# RTX USD Viewer

## 🚀 PROJECT VIDEO AND ARTICLE COMING SOON!!

A real-time **USD scene viewer** that runs in the browser. It uses NVIDIA's `ovrtx` (Omniverse RTX) Python package to render locally with RTX, then streams JPEG frames to a web UI over WebSocket. You can load any local USD scene, inspect the prim hierarchy, pick prims by clicking the rendered image, and transform the selected prim.

This project is intended as a **minimal, hackable reference** for building browser-based RTX tools on top of Omniverse libraries.

<img src="_images/ovrtx-usd-viewer-thumb.png" alt="Project Screenshot" width="600"/>

---

## What you can do

- Stream an RTX-rendered view to any browser tab on the same machine.
- Load a USD scene by path or by using the OS file picker.
- List every prim in the scene and select one from the sidebar.
- Click on the rendered image to pick a prim under the cursor.
- Translate, rotate, and scale the selected prim.
- Move the default camera with simple sidebar controls.
- Auto-reconnect if the server restarts.

---

## Requirements

- **Windows or Linux** with an NVIDIA RTX-capable GPU. (Windows is the primary platform tested; Linux should work with the same NVIDIA `ovrtx` stack.)
- **Python 3.10+**.
- **USD Scenes**: For USD scenes to load properly, they must include a light and a camera. Simple scenes are more likely to work in this viewer POC. Working samples are provided in the `usd_samples` directory.        

---

> The commands below use `ovrtx_env` as the environment name and `uv`, which is the required installer for `ovrtx`. If you prefer a different environment name or environment manager, replace accordingly. You will not be able to pip install the `ovrtx` package until NVIDIA publishes it to PyPI.

---

## Installation

The following workflow creates a conda environment, installs `uv`, pulls the `ovrtx` package with `uv`, and installs the web-server dependencies from this repo.

1. **Create and activate a conda environment.**

   ```powershell
   conda create -n ovrtx_env python=3.12
   conda activate ovrtx_env
   ```

2. **Install `uv`.**

   ```powershell
   pip install uv
   ```

3. **Add `ovrtx` and the web dependencies.**

   ```powershell
   uv add ovrtx
   ```

4. **Clone this repository and enter it.**

   ```powershell
   git clone <repo-url>
   cd nvidia-ovrtx-usd-viewer
   ```

---

## Run

Start the server with live-streamed logs:

```powershell
python -m rtx_viewer.server
```

Then open [http://localhost:8080](http://localhost:8080) in your browser.

The server will boot the RTX renderer, then wait for a browser connection. The first client that connects triggers the default scene load (`usd_samples/simple_scene.usda`). Frames are only rendered while at least one browser tab is connected and a scene is loaded, so the GPU stays idle otherwise.

---

## Using the UI

1. **Scene loading**
   - Paste a full USD path into the *Scene path* box and click **Load**.
   - Or click **Browse...** to open the OS file picker, select a `.usd`, `.usda`, or `.usdc` file, and let it upload and load automatically.
2. **Prim inspection**
   - Click **List prims** to populate the sidebar.
   - Click any prim in the list to select it.
3. **Picking**
   - Click directly on the rendered image to pick the prim under the cursor.
4. **Transform**
   - Once a prim is selected, use the **Translate**, **Rotate**, and **Scale** buttons. The change is applied on the server and the next streamed frame reflects it.
5. **Camera**
   - Use the **Camera** buttons to slide the active camera along the world axes.

> The viewer auto-discovers the first `RenderProduct` and a sensible `Camera` from each scene. If your scene has multiple cameras or custom render products, the first non-test camera is preferred.

---

## Architecture

```
┌─────────────┐      WebSocket / JPEG      ┌─────────────────────┐
│  Browser    │  ◄──────────────────────►   │  FastAPI server     │
│  (web/)     │   REST / file upload       │  (src/rtx_viewer/)  │
└─────────────┘                            └──────────┬──────────┘
                                                       │
                                            ┌──────────▼──────────┐
                                            │  RTXViewerRenderer  │
                                            │  (thread-safe wrap) │
                                            └──────────┬──────────┘
                                                       │
                                            ┌──────────▼──────────┐
                                            │  ovrtx.Renderer     │
                                            │  (RTX / USD)        │
                                            └─────────────────────┘
```

### Key files

| File | Purpose |
|------|---------|
| `src/rtx_viewer/renderer.py` | Thread-safe wrapper around `ovrtx.Renderer`. Handles scene loading, frame rendering, picking, selection outline, and prim transforms. |
| `src/rtx_viewer/server.py` | FastAPI application. Serves the static UI, exposes HTTP endpoints, streams frames over WebSocket, and routes commands to the renderer. |
| `web/index.html` | UI layout. |
| `web/app.js` | WebSocket client, frame rendering, and interaction handling. |
| `web/style.css` | Dark theme layout. |
| `scripts/` | Standalone helpers to verify the environment, the renderer, and the WebSocket pipeline. |

### WebSocket protocol

Text messages are JSON. Binary messages are JPEG frames.

**Client → Server commands**

| Command | Fields | Effect |
|---------|--------|--------|
| `load` | `path`, optional `render_product`, optional `camera_path` | Open a USD scene. |
| `list_prims` | — | Return all prim paths. |
| `pick` | `x`, `y` (normalized 0..1) | Pick the prim at screen coordinates. |
| `select` | `path` | Highlight a prim. |
| `translate` | `path` (optional, defaults to selected), `dx`, `dy`, `dz` | Move a prim. |
| `rotate` | `path` (optional, defaults to selected), `axis`, `degrees` | Rotate a prim. |
| `scale` | `path` (optional, defaults to selected), `sx`, `sy`, `sz` | Scale a prim. |
| `camera` | `dx`, `dy`, `dz` | Move the active camera. |

**Server → Client responses**

All responses include `{ok: true, cmd: ...}` or `{ok: false, error: ...}`. The `load` response also includes the discovered `render_product` and `camera_path`.

### HTTP endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /` | Serve the main UI. |
| `GET /api/default_scene` | Return the default USD path. |
| `GET /api/prims` | Return the list of prim paths. |
| `GET /api/selected` | Return the currently selected prim path. |
| `POST /api/upload_scene` | Accept a `.usd/.usda/.usdc` file upload, save it to `uploads/`, and return the server-side path. |

---

## Development helpers

The `scripts/` folder contains small standalone tools:

| Script | Use |
|--------|-----|
| `scripts/check_env.py` | Verify that `ovrtx` and the web server dependencies are importable. |
| `scripts/render_test.py` | Load a built-in ovrtx test scene and save a single PNG to `output/`. |
| `scripts/test_wrapper.py` | Test the `RTXViewerRenderer` wrapper directly (load, render, pick). |
| `scripts/test_ws_client.py` | Connect to the running server, load the default scene, and receive a frame. |
| `scripts/test_upload.py` | Upload a USD file via the HTTP endpoint. |
| `scripts/test_upload_and_load.py` | Upload a USD file and load it over WebSocket. |

Run any of them with `uv run`, for example:

```powershell
uv run python scripts/render_test.py
```

Or with the conda environment directly:

```powershell
conda activate ovrtx_env
python scripts/render_test.py
```

---

## Troubleshooting

- **Black screen on first load**: The RTX renderer may need a few seconds to compile shaders and build the scene. Wait for the status bar to show `Loaded ...`.
- **Missing texture warnings**: Warnings like `checkerboard.png` not found are harmless if the material still renders. Copy the referenced texture next to the USD file to resolve them.
- **Wrong camera**: The auto-discovery prefers the first non-test camera. If a scene has unusual camera names, you can extend `RTXViewerRenderer._pick_main_camera` or load with an explicit `camera_path`.
- **Port 8080 is in use**: Change the port in `src/rtx_viewer/server.py` in the `main()` function, or set `PORT` in the environment and restart.

---

## License

MIT License — see `LICENSE` for details.
