"""API smoke tests (mock mode, no external services)."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.session import init_db
from app.main import app
from app.rag.ingestion import seed_knowledge_base


@pytest.fixture(scope="session", autouse=True)
def _seed():
    seed_knowledge_base(force=True)


@pytest_asyncio.fixture(autouse=True)
async def _db():
    await init_db()


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["mock_mode"] is True
    assert "llm_backend" in data
    assert "knowledge_docs" in data


@pytest.mark.asyncio
async def test_diagnose_network_timeout():
    transport = ASGITransport(app=app)
    logs = (
        "Error: connect ETIMEDOUT registry.npmjs.org\n"
        "npm ERR! network Temporary network failure\n"
        "Process completed with exit code 1.\n"
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/failures/diagnose",
            json={
                "repo": "demo/app",
                "workflow_name": "CI",
                "job_name": "build",
                "raw_logs": logs,
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["classification"]
    assert data["root_cause"]
    assert data["suggested_fix"]
    assert data["confidence"] is not None
    assert data["remediation_action"] in {
        "retry_workflow",
        "needs_approval",
        "none",
        "clear_cache",
        "pin_dependency",
    }


@pytest.mark.asyncio
async def test_dashboard_stats():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/dashboard/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_failures" in data
    assert "recent_failures" in data


@pytest.mark.asyncio
async def test_list_samples():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/samples")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 3
    assert "content" in data[0]
