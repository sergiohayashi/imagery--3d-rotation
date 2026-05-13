# imagery-simulator

**imagery-simulator** can run in two ways:

- **CLI** — run evaluations and experiments from the command line (this is how experiments are executed).
- **API** — serve HTTP endpoints so the frontend can browse and inspect full resolution threads (all iterations).

Repository-wide context (paper, `data/` layout, frontend) is in the [root `README.md`](../README.md).

## Setup

### 1. Environment variables

The app loads `./.env.local-only` from this directory (see `app/config/config.py`). Copy the template and fill in real values; do not commit secrets.

```bash
cp .env.example .env.local-only
# Edit .env.local-only
```

You need working infrastructure and API keys for what the code uses, including **MongoDB**, and **OpenAI** (and optionally other providers such as Gemini). See `.env.example` for variable names (`MONGO_*`, `OPENAI_API_KEY`, etc.).

### 2. Virtual environment and dependencies

**Requirement:** Python 3.12 or later.

Create a virtual environment, activate it, and install packages from `requirements.txt`:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Use this same environment for the CLI and for `uvicorn`.

## CLI — experiments

**Run experiments in CLI mode** (with the venv activated):

`eval08101_p3_f1` examples:

```bash
# Run eval08101_p3_f1 on a single problem (id 0)
python -m app.cli.main eval08101_p3_f1 --list 0

# Run eval08101_p3_f1 on the full dataset (40 problems)
python -m app.cli.main eval08101_p3_f1

# Run with a specific reasoning model
python -m app.cli.main eval08101_p3_f1 --reasoning-model gpt-5.2-2025-12-11
```

## API — web server (for the UI)

To **visualize all iterations** in the browser, run this service and the [`frontend`](../frontend/) app (see the root README). From this directory, with the venv activated:

```bash
uvicorn app.web.main:app --port 8000
```

The frontend expects the API at **`http://localhost:8000`** ([`frontend/src/config.js`](../frontend/src/config.js)). If you change the host or port, update `apiUrl` there (or adjust your setup accordingly).

## Viewing results

- **Artifacts on disk** — JSON and related outputs under the repo’s [`data/`](../data/) tree (e.g. `data/spatialviz/results/`); generated images may also live under paths such as `data/__local_bucket__` depending on configuration.
- **Full UI** — API + frontend as above.



