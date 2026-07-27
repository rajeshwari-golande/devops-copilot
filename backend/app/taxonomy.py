"""
Failure taxonomy grounded in published sources (free / public).

References:
- Google SRE Book — incident / failure thinking (sre.google/books)
- GitLab public incident handbook / postmortem practice
  (about.gitlab.com/handbook — production incident culture)
- Flaky-test research (e.g. iDFlakies and related work on non-deterministic tests)

We map CI/CD failures into a small, interview-defensible set of classes.
"""

from __future__ import annotations

from typing import Final

# Canonical labels used by agent, seed KB, samples, and eval harness
TAXONOMY: Final[dict[str, dict[str, str]]] = {
    "transient_network": {
        "description": "Temporary network / registry / CDN failures",
        "source": "Common CI ops class; aligns with SRE 'transient' dependency failures",
        "safe_default_action": "retry_workflow",
    },
    "dependency_conflict": {
        "description": "Lockfile / resolver / incompatible package pins",
        "source": "SRE dependency / change-failure patterns",
        "safe_default_action": "pin_dependency",
    },
    "resource_exhaustion": {
        "description": "OOM, disk, CPU limits (e.g. exit 137)",
        "source": "SRE capacity / resource saturation",
        "safe_default_action": "clear_cache",
    },
    "test_failure": {
        "description": "Assert failures, import errors, broken tests",
        "source": "Flaky-test literature + deterministic test regressions",
        "safe_default_action": "none",
    },
    "flaky_test": {
        "description": "Non-deterministic / racey tests that pass on retry",
        "source": "Academic flaky-test taxonomies (e.g. iDFlakies-style categories)",
        "safe_default_action": "retry_workflow",
    },
    "misconfiguration": {
        "description": "Missing secrets, wrong env, bad workflow config",
        "source": "GitLab-style change/config incident classes",
        "safe_default_action": "none",
    },
    "compile_error": {
        "description": "TypeScript/Java/etc. compile or type errors",
        "source": "Build-phase failure class (change-induced)",
        "safe_default_action": "none",
    },
    "permissions": {
        "description": "Token / GITHUB_TOKEN / IAM permission denials",
        "source": "Access-control incident class",
        "safe_default_action": "none",
    },
    "unknown": {
        "description": "Unclassified — force human review",
        "source": "Fallback",
        "safe_default_action": "needs_approval",
    },
}

CANONICAL_LABELS: Final[frozenset[str]] = frozenset(TAXONOMY.keys())


def normalize_classification(label: str | None) -> str:
    if not label:
        return "unknown"
    key = label.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "network_timeout": "transient_network",
        "network": "transient_network",
        "oom": "resource_exhaustion",
        "out_of_memory": "resource_exhaustion",
        "deps": "dependency_conflict",
        "dependency": "dependency_conflict",
        "secret": "misconfiguration",
        "config": "misconfiguration",
        "typescript": "compile_error",
        "type_error": "compile_error",
        "flake": "flaky_test",
        "flaky": "flaky_test",
        "permission": "permissions",
        "authz": "permissions",
    }
    key = aliases.get(key, key)
    return key if key in CANONICAL_LABELS else "unknown"
