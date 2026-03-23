# Frontend — experiment browser

React UI for this repository’s **imagery reasoning** work. Full project context, the paper, and how `api/`, `frontend/`, and `data/` fit together are in the [root `README.md`](../README.md).

## What this app does in the system

The backend pairs a **Reasoning Module** (a frontier multimodal LLM) with an **Imagery Module** (Python rendering of 3D rotations) on **SpatialViz** mental-rotation tasks. **Experiments are run from the CLI** in [`api/`](../api/); outputs land under [`data/`](../data/).

This **frontend** is for **inspecting results in the browser**: full resolution threads—each model turn, rendered snapshots, and the structured trace—by talking to the **`api` HTTP service**. Reading JSON under `data/` directly is enough for raw artifacts; the UI is optional but best for **all iterations** end-to-end.

**API URL and port** — The app expects the backend at **`http://localhost:8000`**, set in [`src/config.js`](src/config.js) as `apiUrl`. Start Uvicorn on port **8000** (see [`api/README.md`](../api/README.md)). If you run the API elsewhere, change `apiUrl` to match.

Start the [API](../api/README.md) (`uvicorn`) before `npm start`, and configure [`api/.env.local-only`](../api/.env.example) so the stack can reach MongoDB, storage, and model services as needed.

## Scripts

From this directory:

```bash
npm install
```

**Development** — dev server with reload (default [http://localhost:3000](http://localhost:3000)):

```bash
npm start
```

**Production build** — output in `build/`:

```bash
npm run build
```

Bootstrapped with [Create React App](https://github.com/facebook/create-react-app).
