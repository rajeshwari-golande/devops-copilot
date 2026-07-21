"""LangGraph diagnosis agent + Groq / Ollama / heuristic fallbacks."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypedDict

from app.agent.prompts import DIAGNOSE_USER_TEMPLATE, SYSTEM_PROMPT
from app.config import get_settings
from app.rag.chroma_store import query_similar

logger = logging.getLogger(__name__)

SAFE_ACTIONS = {"retry_workflow", "clear_cache", "pin_dependency"}


class AgentState(TypedDict, total=False):
    logs: str
    similar_cases: list[dict[str, Any]]
    diagnosis: dict[str, Any]


def _format_similar(cases: list[dict[str, Any]]) -> str:
    if not cases:
        return "(no similar cases in knowledge base yet)"
    parts: list[str] = []
    for i, case in enumerate(cases, 1):
        meta = case.get("metadata") or {}
        parts.append(
            f"{i}. classification={meta.get('classification')}\n"
            f"   root_cause={meta.get('root_cause')}\n"
            f"   fix={meta.get('fix')}\n"
            f"   safe_action={meta.get('safe_action')}\n"
            f"   distance={case.get('distance')}"
        )
    return "\n".join(parts)


def _normalize_diagnosis(data: dict[str, Any], similar: list[dict[str, Any]], source: str) -> dict[str, Any]:
    action = data.get("remediation_action", "needs_approval")
    if action not in SAFE_ACTIONS | {"none", "needs_approval"}:
        action = "needs_approval"
    auto_safe = bool(data.get("auto_apply_safe")) and action in SAFE_ACTIONS
    reasoning = data.get("agent_reasoning", "")
    if source and source not in reasoning:
        reasoning = f"[{source}] {reasoning}".strip()
    return {
        "classification": data.get("classification", "unknown"),
        "root_cause": data.get("root_cause", ""),
        "suggested_fix": data.get("suggested_fix", ""),
        "confidence": float(data.get("confidence", 0.5)),
        "remediation_action": action if auto_safe or action == "none" else "needs_approval",
        "auto_apply_safe": auto_safe,
        "agent_reasoning": reasoning,
        "similar_cases": similar,
    }


def _heuristic_diagnosis(logs: str, similar: list[dict[str, Any]]) -> dict[str, Any]:
    """Rule + RAG fallback when Groq/Ollama is unavailable (MOCK_MODE / no key)."""
    lower = logs.lower()
    if similar:
        best = similar[0]
        meta = best.get("metadata") or {}
        action = meta.get("safe_action") or "none"
        return {
            "classification": meta.get("classification", "unknown"),
            "root_cause": meta.get("root_cause", "Matched historical failure pattern"),
            "suggested_fix": meta.get("fix", "Review similar cases and apply the known fix"),
            "confidence": max(0.55, 1.0 - float(best.get("distance") or 0.4)),
            "remediation_action": action if action in SAFE_ACTIONS else "needs_approval",
            "auto_apply_safe": action in SAFE_ACTIONS,
            "agent_reasoning": (
                "[rag+heuristic] Retrieved nearest Chroma neighbor and mapped its known fix. "
                "Set GROQ_API_KEY + MOCK_MODE=false (or PREFER_OLLAMA=true) for LLM diagnosis."
            ),
            "similar_cases": similar,
        }

    patterns = [
        (
            r"package-lock\.json|npm ci",
            "dependency_conflict",
            "Lockfile out of sync with package.json",
            "Regenerate and commit package-lock.json",
            "none",
        ),
        (
            r"etimedout|temporary failure|econnreset",
            "transient_network",
            "Transient network / registry timeout",
            "Re-run the workflow; add retries for registry fetches",
            "retry_workflow",
        ),
        (
            r"exit code 137|out of memory|oom",
            "resource_exhaustion",
            "Process exceeded memory and was OOM-killed",
            "Reduce heap / clear build cache / split jobs",
            "clear_cache",
        ),
        (
            r"modulenotfounderror|no module named",
            "test_failure",
            "Missing Python module / incorrect PYTHONPATH",
            "Install package editable or set PYTHONPATH in CI",
            "none",
        ),
        (
            r"secret .* not found|required secret",
            "misconfiguration",
            "Missing GitHub Actions secret",
            "Add the secret in repository settings and re-run",
            "none",
        ),
        (
            r"ts\d{4}|typescript",
            "compile_error",
            "TypeScript compile/type error",
            "Fix the reported type error and re-run the build job",
            "none",
        ),
        (
            r"resolutionimpossible|could not find a version that satisfies",
            "dependency_conflict",
            "Conflicting Python dependency pins",
            "Align package versions and regenerate the lockfile",
            "pin_dependency",
        ),
    ]
    for pattern, classification, cause, fix, action in patterns:
        if re.search(pattern, lower):
            return {
                "classification": classification,
                "root_cause": cause,
                "suggested_fix": fix,
                "confidence": 0.7,
                "remediation_action": action if action in SAFE_ACTIONS else "needs_approval",
                "auto_apply_safe": action in SAFE_ACTIONS,
                "agent_reasoning": f"[heuristic] Regex match on pattern `{pattern}`.",
                "similar_cases": similar,
            }

    return {
        "classification": "unknown",
        "root_cause": "Could not confidently classify from logs alone",
        "suggested_fix": "Manual triage required — attach full job log and failing step",
        "confidence": 0.3,
        "remediation_action": "needs_approval",
        "auto_apply_safe": False,
        "agent_reasoning": "[heuristic] No RAG hit and no pattern matched.",
        "similar_cases": similar,
    }


def _parse_llm_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _invoke_chat(messages: list, settings) -> tuple[str, str]:
    """Try Groq first (unless prefer_ollama), then Ollama."""
    backends: list[str] = []
    if settings.prefer_ollama:
        backends.append("ollama")
        if settings.groq_api_key:
            backends.append("groq")
    else:
        if settings.groq_api_key:
            backends.append("groq")
        backends.append("ollama")

    last_error: Exception | None = None
    for name in backends:
        try:
            if name == "groq":
                from langchain_groq import ChatGroq

                llm = ChatGroq(
                    api_key=settings.groq_api_key,
                    model_name=settings.groq_model,
                    temperature=0.1,
                )
            else:
                try:
                    from langchain_ollama import ChatOllama
                except ImportError:
                    from langchain_community.chat_models import ChatOllama

                llm = ChatOllama(
                    base_url=settings.ollama_base_url,
                    model=settings.ollama_model,
                    temperature=0.1,
                )
            response = llm.invoke(messages)
            content = response.content if isinstance(response.content, str) else str(response.content)
            return content, name
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning("%s backend failed: %s", name, exc)
    raise RuntimeError(f"All LLM backends failed: {last_error}")


def _llm_diagnose(logs: str, similar: list[dict[str, Any]]) -> dict[str, Any]:
    settings = get_settings()
    prompt = DIAGNOSE_USER_TEMPLATE.format(
        logs=logs[:8000],
        similar_cases=_format_similar(similar),
    )

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        content, source = _invoke_chat(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)],
            settings,
        )
        data = _parse_llm_json(content)
        return _normalize_diagnosis(data, similar, source)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM diagnosis failed (%s); falling back to heuristics", exc)
        return _heuristic_diagnosis(logs, similar)


def retrieve_node(state: AgentState) -> AgentState:
    logs = state["logs"]
    similar = query_similar(logs[:3000], n_results=5)
    return {**state, "similar_cases": similar}


def diagnose_node(state: AgentState) -> AgentState:
    settings = get_settings()
    similar = state.get("similar_cases") or []
    if settings.use_llm or (not settings.mock_mode and (settings.groq_api_key or settings.prefer_ollama)):
        diagnosis = _llm_diagnose(state["logs"], similar)
    else:
        diagnosis = _heuristic_diagnosis(state["logs"], similar)
    return {**state, "diagnosis": diagnosis}


def build_diagnosis_graph():
    """Build LangGraph StateGraph when langgraph is available; else linear pipeline."""
    try:
        from langgraph.graph import END, StateGraph

        graph = StateGraph(AgentState)
        graph.add_node("retrieve", retrieve_node)
        graph.add_node("diagnose", diagnose_node)
        graph.set_entry_point("retrieve")
        graph.add_edge("retrieve", "diagnose")
        graph.add_edge("diagnose", END)
        return graph.compile()
    except Exception as exc:  # noqa: BLE001
        logger.warning("LangGraph unavailable (%s); using linear pipeline", exc)
        return None


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_diagnosis_graph()
    return _GRAPH


def run_diagnosis(logs: str) -> dict[str, Any]:
    """Public entry: retrieve similar cases → diagnose → return structured result."""
    graph = get_graph()
    initial: AgentState = {"logs": logs}
    if graph is not None:
        final = graph.invoke(initial)
        return final.get("diagnosis") or _heuristic_diagnosis(logs, final.get("similar_cases") or [])

    mid = retrieve_node(initial)
    final = diagnose_node(mid)
    return final["diagnosis"]
