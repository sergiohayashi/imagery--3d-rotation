# Limits of Imagery Reasoning in Frontier LLM Models

Research code for the paper *Limits of Imagery Reasoning in Frontier LLM Models* (Hayashi & Hirata, Institute of Mathematics and Statistics, University of São Paulo).

**Project page:** [github.com/sergiohayashi/imagery--3d-rotation](https://github.com/sergiohayashi/imagery--3d-rotation)

## What this repository implements

Large language models still struggle on spatial tasks that call for mental simulation—classic **mental rotation** is a clear example. This work tests whether an external **Imagery Module** (Python code that maintains 3D state, applies rotations, and returns rendered snapshots) can act as a “cognitive prosthetic” when paired with a **Reasoning Module** (a frontier multimodal LLM) in a turn-based visual feedback loop.

The system follows a **dual-module, agentic architecture**: the LLM issues rotation commands in intuitive camera-space terms; the imagery side updates pose and returns 2D views. Experiments use the **SpatialViz** 3D rotation benchmark ([SpatialViz-Bench](https://arxiv.org/abs/2507.07610)). Despite extensive prompting and tool use, accuracy in the main incremental-rotation setting peaked around **62.5%**, well below human performance. Follow-up analyses (including small-angle rotation probes and comparisons with specialized geometry models) point to limits in **motion sensitivity**, **dynamic prediction**, and **visual–symbolic balance** rather than a lack of rendered images alone.

The paper uses “functional aphantasia” **only as a metaphor** for these operational deficits in models; it is not a claim about human cognition or clinical conditions.

## Repository layout

This is a **multi-project** layout: runnable applications live under separate top-level folders; shared assets and run outputs live under `data/`.

| Path | Role |
|------|------|
| [`api/`](api/) | Backend (“imagery-simulator”): **command-line mode** for running evaluations, optional **web API** for the UI, imagery pipeline (e.g. PyVista rendering), persistence and file handling. See [`api/README.md`](api/README.md). |
| [`frontend/`](frontend/) | React (Create React App) UI for browsing and inspecting experiment material. See [`frontend/README.md`](frontend/README.md). |
| [`data/`](data/) | **Problem data** and **experiment artifacts** (e.g. SpatialViz-oriented problems under `data/spatialviz/problems/`, evaluation outputs under `data/spatialviz/results/`). |

## Running experiments and services

### 1. Configure infrastructure and secrets

Before running evaluations or the API, you need working **infrastructure** and credentials. The backend expects:

- **MongoDB** — application data and metadata (connection URL, database name; optional auth).
- **OpenAI API** — API key for the reasoning model (and optionally other providers supported by the code, e.g. Gemini).

Copy the template and fill in real values **inside `api/`** (the app loads `./.env.local-only` relative to that package):

```bash
cp api/.env.example api/.env.local-only
# Edit api/.env.local-only — do not commit secrets
```

Relevant variables are documented in [`api/.env.example`](api/.env.example) (`MONGO_*`, `OPENAI_API_KEY`, etc.).

### 2. Python environment (`api/`)

**Requirement:** Python 3.12 or later.

Create a virtual environment in the `api` project, activate it, and install dependencies from [`api/requirements.txt`](api/requirements.txt):

```bash
cd api
python --version    #ensure python 3.12 or later
python -m venv .venv   
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Use this same environment whenever you run the CLI, `uvicorn`, or other Python commands for `api/`.

### 3. Run experiments (command-line mode, `api/`)

With the virtual environment from step 2 activated, **run experiments through the CLI of the `api` project**, not through the browser. From the `api` directory, use `python -m app.cli.main` with the evaluation command you need (see [`api/README.md`](api/README.md) for the full list).

Run an evalutation:

```bash
cd api
# run the first problem, using the evaluation setup eval08101_p3_f1
python -m app.cli.main eval08101_p3_f1 --list 0    
```

More samples:
```bash
python -m app.cli.main eval08101_p3_f1 --list 0 --reasoning-model gpt-5.2-2025-12-11
# OR run full test (take hours..)
python -m app.cli.main eval08101_p3_f1 --reasoning-model gpt-5.2-2025-12-11
# OR run a range
python -m app.cli.main eval08101_p3_f1 --start 0 --end 10    
```


### 4. View results

How you inspect outputs depends on how much detail you need:

- **Files in `data/`** — After a run, you can open the generated JSON and related artifacts directly under [`data/`](data/) (for example under `data/spatialviz/results/`). No web stack is required for that.
    - The generate images are saved under the folder `data/__local_bucket__`
- **All iterations in the UI** — To browse **full resolution threads** (every model turn, imagery snapshots, and the structured trace the app expects), run the **`api` as a web server**, run the **`frontend`**, and open the application in a **browser**. The frontend talks to the API to load runs end-to-end.

The frontend is configured to call the API at **`http://localhost:8000`** (see [`frontend/src/config.js`](frontend/src/config.js)). Run `uvicorn` on that port (the default for Uvicorn is 8000).

Start the API (from `api/`, with the same virtual environment activated):

```bash
cd api
uvicorn app.web.main:app --port 8000
```

Start the frontend (from `frontend/`):

```bash
cd frontend
npm install
npm start
```

Then open the dev server URL shown in the terminal (typically [http://localhost:3000](http://localhost:3000)) and use the app as configured for your environment.

## Citation

If you use this code or the associated study, please cite the paper (final bibliographic details will match your published version). The SpatialViz benchmark is described in Wang et al., *SpatialViz-Bench: An MLLM Benchmark for Spatial Visualization*, [arXiv:2507.07610](https://arxiv.org/abs/2507.07610).

## License

Refer to the authors for terms of use if no license file is provided in the repository.
