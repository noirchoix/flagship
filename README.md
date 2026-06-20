# Flagship AI Suite API

Unified Render backend for the live flagship portfolio apps.

Included modules:

- AI Workflow Builder: `/api/v1/workflows`
- BioDataset Scout: `/api/v1/bio-scout`
- Research Assistant: `/api/...`
- FlavourDB/FSBI Workbench: `/api/scrape`
- ShipGate Launch Readiness Auditor: `/api/v1/shipgate`

RegIntel is intentionally excluded from this unified backend because its PDF worker/Redis/Qdrant/Voyage path complicates a free-tier shared deployment. Use a recorded demo/case-study page for RegIntel instead.

The service is designed for Render free/starter constraints: Python 3.11 is pinned, Gunicorn uses one Uvicorn worker by default, request IDs and security headers are added, CORS is controlled by env, SQLite runtime data is kept under `./data`, and heavyweight integrations are optional/offline-safe where possible.

## Render settings

Build command:

```bash
pip install --upgrade pip && pip install -r requirements.txt
```

Start command:

```bash
gunicorn ai_suite.main:app --config gunicorn_conf.py
```

Health check path:

```text
/health
```

Set `PYTHON_VERSION=3.11.9` in Render even though `.python-version` is included.

## Required frontend env

Each deployed frontend should use the Render backend URL:

```env
VITE_API_BASE_URL=https://your-render-service.onrender.com
```

ShipGate also uses the same backend root. Its frontend calls `/api/v1/shipgate/...` automatically.

## Required Render env

Copy `.env.example`, set `AI_SUITE_CORS_ORIGINS` to the comma-separated deployed frontend origins, and add secrets directly in Render. Do not commit real API keys.

Start with these secrets only where needed:

```env
DEEPSEEK_API_KEY=
SERPAPI_API_KEY=
ELEVEN_API_KEY=
BIODATASET_NCBI_API_KEY=
```

ShipGate runs in static/offline audit mode by default:

```env
SHIPGATE_LLM_PROVIDER=offline
```

To enable optional LLM synthesis for ShipGate, set:

```env
SHIPGATE_LLM_PROVIDER=deepseek
SHIPGATE_DEEPSEEK_API_KEY=
```

If `SHIPGATE_DEEPSEEK_API_KEY` is blank, ShipGate falls back to the shared `DEEPSEEK_API_KEY`.

## Local run

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn ai_suite.main:app --reload --port 8000
```

Test:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/readiness
curl http://localhost:8000/api/v1/suite/status
curl http://localhost:8000/api/v1/shipgate/health
```

## Memory and free-tier notes

Keep `WEB_CONCURRENCY=1` and `GUNICORN_THREADS=1` on Render free tier. ShipGate upload size is capped by `SHIPGATE_MAX_UPLOAD_MB`; the default is `25` to avoid memory spikes from large ZIP uploads. Runtime SQLite files and uploads are stored under `./data`, which is ephemeral on free hosting.
