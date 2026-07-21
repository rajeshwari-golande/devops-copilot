"""Seed and ingest failure knowledge into ChromaDB."""

from __future__ import annotations

from typing import Any

from app.rag.chroma_store import add_knowledge

# Curated failure patterns — mirrors real CI issues (npm, pytest, docker, OOM, secrets).
SEED_KNOWLEDGE: list[dict[str, Any]] = [
    {
        "id": "npm-lockfile-mismatch",
        "classification": "dependency_conflict",
        "document": (
            "Error: npm ci failed. package-lock.json out of sync with package.json. "
            "npm ERR! `npm ci` can only install packages when your package.json and "
            "package-lock.json are in sync."
        ),
        "root_cause": "package-lock.json is out of sync with package.json",
        "fix": "Run `npm install` locally, commit the updated package-lock.json, and re-run CI.",
        "safe_action": "none",
    },
    {
        "id": "pytest-import-error",
        "classification": "test_failure",
        "document": (
            "ModuleNotFoundError: No module named 'app'. pytest collected 0 items / "
            "ImportError during collection. PYTHONPATH not set for backend package."
        ),
        "root_cause": "Python package path not on PYTHONPATH / missing editable install",
        "fix": "Add `PYTHONPATH=backend` or `pip install -e .` in the CI job before pytest.",
        "safe_action": "none",
    },
    {
        "id": "docker-oom",
        "classification": "resource_exhaustion",
        "document": (
            "Container killed with exit code 137. Out of memory. "
            "Java build / webpack heap OOM during docker build on free runner."
        ),
        "root_cause": "Build process exceeded runner memory (OOM kill, exit 137)",
        "fix": "Lower Node/Java heap, split jobs, or use a larger runner. Clear Docker build cache.",
        "safe_action": "clear_cache",
    },
    {
        "id": "flake-network-timeout",
        "classification": "transient_network",
        "document": (
            "Error: connect ETIMEDOUT registry.npmjs.org. "
            "Failed to fetch https://pypi.org/simple/. Temporary network failure."
        ),
        "root_cause": "Transient network timeout talking to package registry",
        "fix": "Re-run the workflow; optionally add retry logic for registry fetches.",
        "safe_action": "retry_workflow",
    },
    {
        "id": "gh-actions-secret-missing",
        "classification": "misconfiguration",
        "document": (
            "Error: Secret GROQ_API_KEY not found. "
            "Required secret or variable is not set in repository settings."
        ),
        "root_cause": "Required GitHub Actions secret is missing from repository settings",
        "fix": "Add the secret under Settings → Secrets and variables → Actions, then re-run.",
        "safe_action": "none",
    },
    {
        "id": "typescript-type-error",
        "classification": "compile_error",
        "document": (
            "error TS2345: Argument of type 'string | undefined' is not assignable "
            "to parameter of type 'string'. TypeScript build failed."
        ),
        "root_cause": "TypeScript type error — possibly undefined value passed where string required",
        "fix": "Add a null/undefined guard or narrow the type before the call site.",
        "safe_action": "none",
    },
    {
        "id": "pip-resolution-conflict",
        "classification": "dependency_conflict",
        "document": (
            "ERROR: Cannot install pydantic==1.10 and pydantic==2.9. ResolutionImpossible. "
            "pip could not find a version that satisfies the requirement."
        ),
        "root_cause": "Conflicting Python dependency pins in requirements",
        "fix": "Align package versions (prefer pydantic v2), regenerate lockfile, pin consistently.",
        "safe_action": "pin_dependency",
    },
    {
        "id": "permission-denied-checkout",
        "classification": "permissions",
        "document": (
            "Error: Resource not accessible by integration. "
            "GITHUB_TOKEN lacks contents:write or actions:write permission."
        ),
        "root_cause": "Workflow token permissions are too restrictive for the requested action",
        "fix": "Grant the needed permissions in the workflow `permissions:` block or use a PAT.",
        "safe_action": "none",
    },
]


def seed_knowledge_base(force: bool = False) -> int:
    from app.rag.chroma_store import ensure_collection

    collection = ensure_collection()
    if collection.count() > 0 and not force:
        return 0

    documents = [item["document"] for item in SEED_KNOWLEDGE]
    metadatas = [
        {
            "classification": item["classification"],
            "root_cause": item["root_cause"],
            "fix": item["fix"],
            "safe_action": item["safe_action"],
            "source": "seed",
        }
        for item in SEED_KNOWLEDGE
    ]
    ids = [item["id"] for item in SEED_KNOWLEDGE]
    add_knowledge(documents, metadatas, ids)
    return len(ids)


def ingest_feedback_as_knowledge(
    failure_logs: str,
    root_cause: str,
    fix: str,
    classification: str = "engineer_corrected",
) -> str:
    doc = f"Failure logs excerpt:\n{failure_logs[:2000]}\n\nRoot cause: {root_cause}\nFix: {fix}"
    ids = add_knowledge(
        [doc],
        [
            {
                "classification": classification,
                "root_cause": root_cause,
                "fix": fix,
                "safe_action": "none",
                "source": "feedback",
            }
        ],
    )
    return ids[0]
