"""Agent heuristic / RAG unit tests (no LLM required)."""

from app.agent.graph import run_diagnosis
from app.rag.ingestion import seed_knowledge_base


def setup_module():
    seed_knowledge_base(force=True)


def test_network_timeout_prefers_retry():
    logs = (
        "Error: connect ETIMEDOUT registry.npmjs.org\n"
        "npm ERR! network Temporary network failure\n"
    )
    result = run_diagnosis(logs)
    assert result["classification"]
    assert result["confidence"] >= 0.5
    assert result["remediation_action"] in {
        "retry_workflow",
        "needs_approval",
        "none",
        "clear_cache",
        "pin_dependency",
    }


def test_oom_suggests_clear_cache_or_known_class():
    logs = "Container killed with exit code 137. Out of memory during npm run build.\n"
    result = run_diagnosis(logs)
    assert result["classification"] in {"resource_exhaustion", "unknown"} or result["root_cause"]
    assert "suggested_fix" in result
