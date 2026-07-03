# RTX USD Viewer

A real-time USD scene viewer that runs in the browser. It uses the NVIDIA `ovrtx` package to render with RTX and streams frames to a web UI over WebSocket. You can load any local USD scene, inspect the prim hierarchy, pick prims by clicking the rendered image, and transform the selected prim.

## Requirements

- Windows with an NVIDIA RTX-capable GPU
- A conda environment named `ovlibraries` containing `ovrtx`
- `uv` installed in the conda environment

## Installation

Activate the conda environment and install the web dependencies with `uv`:

```powershell
conda activate ovlibraries
uv pip install -e .
```

Or use the provided script:

```powershell
conda run -n ovlibraries uv pip install -e .
```

## Run

To see server logs in real time from the `ovlibraries` environment without manually activating it, use `--live-stream`:

```powershell
conda run -n ovlibraries --live-stream python -m rtx_viewer.server
```

Or, if you have already activated the environment:

```powershell
conda activate ovlibraries
python -m rtx_viewer.server
```

Then open `http://localhost:8080` in your browser.

## Features

- Streamed RTX-rendered view in the browser
- Load a local USD scene via the sidebar path input
- List all prims in the scene
- Click on the image to pick a prim
- Translate, rotate, and scale the selected prim
- Move the default camera with the sidebar buttons
- Auto-reconnecting WebSocket connection

## Project structure

- `src/rtx_viewer/renderer.py` — `ovrtx` wrapper
- `src/rtx_viewer/server.py` — FastAPI + WebSocket server
- `web/` — HTML, CSS, and JavaScript frontend
- `scripts/` — helper scripts
