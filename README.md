# DevOps Copilot

AI agent for **CI/CD failure diagnosis and safe auto-remediation**.

Built as a free-tier-deployable portfolio project: FastAPI + LangGraph + Groq + ChromaDB RAG + React.

## What it does

1. Ingests GitHub Actions failure webhooks (or manual log paste)
2. Parses / chunks logs and retrieves similar past failures from ChromaDB
3. LangGraph agent (Groq Llama, or heuristic mock mode) classifies → proposes fix → decides safe auto-fix vs needs-approval
4. Safe allowlisted actions only (`retry_workflow`, `clear_cache`, `pin_dependency`) — never arbitrary code execution
5. Posts Slack alerts for risky cases; engineer feedback updates the knowledge base
6. React dashboard shows trends, accuracy, and live diagnoses

## Project layout

```
devops-copilot/
├── backend/app/          # FastAPI app, agent, RAG, services
├── backend/scripts/      # seed KB, demo failure
├── backend/tests/
├── data/sample_failures/ # example CI logs
├── frontend/             # React + Vite + Tailwind (Vercel-ready)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Quick start (local, mock mode — no API keys)

```bash
# 1. Python env
cd devops-copilot
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # or: cp .env.example .env

# 2. Seed knowledge base (also auto-runs on API startup)
$env:PYTHONPATH="backend"   # PowerShell
python backend/scripts/seed_knowledge_base.py

# 3. Run API
uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000

# 4. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Or one-shot setup: `.\scripts\setup.ps1`

Open http://localhost:5173 — pick a **sample pack**, click **Run agent**.

API docs: http://127.0.0.1:8000/docs

### Demo via CLI

```bash
# with API running
python backend/scripts/demo_failure.py
```

### Tests

```bash
$env:PYTHONPATH="backend"
$env:MOCK_MODE="true"
pytest -q
```

## Enable real LLM

**Groq (cloud, free):**
```
MOCK_MODE=false
GROQ_API_KEY=gsk_...
```

**Ollama (local, free):**
```
MOCK_MODE=false
PREFER_OLLAMA=true
OLLAMA_MODEL=llama3.2
```

Local embeddings use `sentence-transformers` (free). If the model can't download, a deterministic hash embedding fallback keeps RAG working for demos/CI.

## GitHub webhook

Point a repository webhook to:

`POST https://<your-render-url>/api/v1/webhooks/github`

Events: `workflow_run`. Set `GITHUB_WEBHOOK_SECRET`, `GITHUB_TOKEN`, `GITHUB_REPO_OWNER`, `GITHUB_REPO_NAME` in `.env`.

## Docker

```bash
copy .env.example .env
docker compose up --build
```

## Free-tier deploy notes

See **[DEPLOY.md](./DEPLOY.md)** for the full checklist (Render API + Vercel UI + webhook + Groq).

| Piece | Suggested free host | Config in repo |
|---|---|---|
| API | Render free | `render.yaml` + slim `Dockerfile` |
| Frontend | Vercel | `frontend/vercel.json` |
| Keep-alive | GitHub Actions cron every 10 min | `.github/workflows/keepalive.yml` |
| Manual remote demo | GitHub Actions | `.github/workflows/demo-diagnose.yml` |
| Postgres | Neon free (or SQLite on Render disk) | `DATABASE_URL` |
| LLM | Groq free / Ollama local | `.env` |
| Vector DB | Chroma (hash embeddings on free Docker) | auto-seeded on boot |

## Interview talking points

- Safe remediation allowlist — production agents must not execute arbitrary fixes
- RAG over historical failures + feedback loop into Chroma
- Free-tier cold-start handled with keep-alive health pings
- Scale path: ECS/GKE workers, managed Postgres + pooling, paid/self-hosted LLM for throughput

## Author

Rajeshwari Golande — SDE + AI/ML + Python
