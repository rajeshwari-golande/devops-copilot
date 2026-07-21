# Windows PowerShell setup for DevOps Copilot
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) {
  python -m venv .venv
}

.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

if (-not (Test-Path .env)) {
  Copy-Item .env.example .env
}

New-Item -ItemType Directory -Force -Path data | Out-Null
$env:PYTHONPATH = "backend"
$env:MOCK_MODE = "true"
.\.venv\Scripts\python backend\scripts\seed_knowledge_base.py

Write-Host ""
Write-Host "Setup complete."
Write-Host "Start API:  .\.venv\Scripts\uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000"
Write-Host "Start UI:   cd frontend; npm install; npm run dev"
