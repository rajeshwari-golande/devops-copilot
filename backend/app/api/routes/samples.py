"""Serve bundled sample CI failure logs for demos."""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import ROOT_DIR
from app.models.schemas import SampleLogOut

router = APIRouter()
SAMPLES_DIR = ROOT_DIR / "data" / "sample_failures"

SAMPLE_META = {
    "npm_network_timeout.log": {
        "title": "npm registry timeout",
        "expected_classification": "transient_network",
        "description": "ETIMEDOUT talking to registry.npmjs.org — safe retry candidate",
    },
    "pytest_import_error.log": {
        "title": "pytest ModuleNotFoundError",
        "expected_classification": "test_failure",
        "description": "Missing `app` package / PYTHONPATH in CI",
    },
    "docker_oom.log": {
        "title": "Docker build OOM (137)",
        "expected_classification": "resource_exhaustion",
        "description": "Build killed — clear cache / lower heap",
    },
    "typescript_error.log": {
        "title": "TypeScript type error",
        "expected_classification": "compile_error",
        "description": "TS2345 — needs human code fix",
    },
    "missing_secret.log": {
        "title": "Missing Actions secret",
        "expected_classification": "misconfiguration",
        "description": "GROQ_API_KEY not configured in repo secrets",
    },
    "pip_conflict.log": {
        "title": "pip ResolutionImpossible",
        "expected_classification": "dependency_conflict",
        "description": "Conflicting pydantic pins — pin_dependency candidate",
    },
}


@router.get("/samples", response_model=list[SampleLogOut])
async def list_samples() -> list[SampleLogOut]:
    if not SAMPLES_DIR.exists():
        return []
    out: list[SampleLogOut] = []
    for path in sorted(SAMPLES_DIR.glob("*.log")):
        meta = SAMPLE_META.get(path.name, {})
        out.append(
            SampleLogOut(
                id=path.stem,
                filename=path.name,
                title=meta.get("title", path.stem),
                description=meta.get("description", ""),
                expected_classification=meta.get("expected_classification"),
                content=path.read_text(encoding="utf-8"),
            )
        )
    return out


@router.get("/samples/{sample_id}", response_model=SampleLogOut)
async def get_sample(sample_id: str) -> SampleLogOut:
    # Allow id with or without .log
    name = sample_id if sample_id.endswith(".log") else f"{sample_id}.log"
    path = SAMPLES_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample not found")
    meta = SAMPLE_META.get(path.name, {})
    return SampleLogOut(
        id=path.stem,
        filename=path.name,
        title=meta.get("title", path.stem),
        description=meta.get("description", ""),
        expected_classification=meta.get("expected_classification"),
        content=path.read_text(encoding="utf-8"),
    )
