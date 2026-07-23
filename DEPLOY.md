# Finish DevOps Copilot — deploy + live demo checklist

## Live URLs (current)

| Piece | URL |
|---|---|
| **Frontend (demo)** | https://devops-copilot-three.vercel.app |
| **API** | https://devops-copilot-l1r8.onrender.com |
| **API health** | https://devops-copilot-l1r8.onrender.com/health |
| **API docs** | https://devops-copilot-l1r8.onrender.com/docs |
| **GitHub** | https://github.com/rajeshwari-golande/devops-copilot |

### Keep-alive (recommended before interviews)

1. Repo → **Settings** → **Secrets and variables** → **Actions** → **Variables**
2. Add `RENDER_HEALTH_URL` = `https://devops-copilot-l1r8.onrender.com/health`
3. Optional: add `DEMO_API_URL` = `https://devops-copilot-l1r8.onrender.com`

The workflow `.github/workflows/keepalive.yml` pings every 10 minutes so Render free tier stays warm.

---

This gets you an interview-ready live demo on free tiers.

## 0) Accounts (all free)

1. [Groq](https://console.groq.com) → create API key (no card)
2. [Render](https://render.com) → sign in with GitHub
3. [Vercel](https://vercel.com) → already usable from CLI / dashboard
4. Optional: [Slack API](https://api.slack.com/apps) bot for alerts

## 1) Deploy API on Render (≈10 min)

1. Render dashboard → **New** → **Blueprint**
2. Connect repo `rajeshwari-golande/devops-copilot`
3. Apply `render.yaml`
4. Set env vars in the service:
   - `CORS_ORIGINS` = your Vercel URL (e.g. `https://devops-copilot.vercel.app`) — update after step 2 if needed; can use `*` temporarily for first bring-up
   - `GROQ_API_KEY` = your Groq key
   - `MOCK_MODE` = `false` (after Groq key is set)
5. Wait for deploy → open `https://<service>.onrender.com/health`
   - Expect `"status":"ok"`, `"knowledge_docs":8`

Cold start: free tier sleeps after ~15 min. Repo already has `.github/workflows/keepalive.yml` —
set GitHub repo variable `RENDER_HEALTH_URL` to `https://<service>.onrender.com/health`.

## 2) Deploy frontend on Vercel

```powershell
cd frontend
# Replace with your Render URL (no trailing slash)
$env:VITE_API_URL = "https://<service>.onrender.com"
npx vercel --prod --yes
```

Or in Vercel project settings → Environment Variables:
- `VITE_API_URL` = `https://<service>.onrender.com`

Then redeploy.

## 3) Wire GitHub webhook (optional but strong for demos)

On any repo (or this one):

1. Settings → Webhooks → Add webhook
2. Payload URL: `https://<service>.onrender.com/api/v1/webhooks/github`
3. Content type: `application/json`
4. Secret: same value as `GITHUB_WEBHOOK_SECRET` on Render
5. Events: **Workflow runs** only
6. On Render set:
   - `GITHUB_TOKEN` = PAT with `actions:read` (and `actions:write` if you want re-run remediation)
   - `GITHUB_REPO_OWNER` / `GITHUB_REPO_NAME`

Fail a workflow → agent diagnoses → dashboard updates.

## 4) Local demo (no deploy)

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "backend"
# optional: set GROQ_API_KEY and MOCK_MODE=false in .env
uvicorn app.main:app --reload --app-dir backend --port 8000
# other terminal
cd frontend; npm run dev
```

Open http://localhost:5173 → sample pack → Run agent.

## Interview talking points

- Safe remediation allowlist (never arbitrary code execution)
- RAG over historical failures + feedback loop
- Free-tier cold-start handled with keep-alive pings
- Scale path: ECS/GKE workers, managed Postgres, paid/self-hosted LLM
