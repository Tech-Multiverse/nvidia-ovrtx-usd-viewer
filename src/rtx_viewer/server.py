"""FastAPI server that streams ovrtx frames and handles prim interaction."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Set

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .renderer import RTXViewerRenderer

logger = logging.getLogger(__name__)

viewer: Optional[RTXViewerRenderer] = None
connected_clients: Set[WebSocket] = set()
render_task: Optional[asyncio.Task] = None

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"
UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"

DEFAULT_SCENE = str(
    Path(__file__).resolve().parent.parent.parent / "usd_samples" / "simple_scene.usda"
)


async def broadcast_frame(frame_bytes: bytes) -> None:
    dead = set()
    for client in connected_clients:
        try:
            await client.send_bytes(frame_bytes)
        except Exception:
            dead.add(client)
    for client in dead:
        connected_clients.discard(client)


async def send_json(client: WebSocket, message: dict) -> None:
    try:
        await client.send_text(json.dumps(message))
    except Exception as exc:
        logger.warning("Failed to send message to client: %s", exc)


async def render_loop() -> None:
    """Continuously render frames and broadcast them as JPEG bytes."""
    while True:
        try:
            if not connected_clients or not viewer.has_scene:
                await asyncio.sleep(0.1)
                continue

            frame = await asyncio.to_thread(viewer.render_frame_jpeg)
            await broadcast_frame(frame)
        except Exception as exc:
            logger.exception("Render loop error: %s", exc)
            await asyncio.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global viewer, render_task
    logging.basicConfig(level=logging.INFO)
    viewer = RTXViewerRenderer(width=1280, height=720)
    render_task = asyncio.create_task(render_loop())
    yield
    if render_task:
        render_task.cancel()
        try:
            await render_task
        except asyncio.CancelledError:
            pass
    if viewer:
        viewer.close()


app = FastAPI(title="RTX USD Viewer", lifespan=lifespan)

if WEB_DIR.exists():
    app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")


@app.get("/")
async def root():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/default_scene")
async def default_scene():
    return {"path": DEFAULT_SCENE}


@app.get("/api/prims")
async def list_prims():
    if not viewer.has_scene:
        return {"prims": []}
    prims = await asyncio.to_thread(viewer.query_prims)
    return {"prims": list(prims.keys())}


@app.post("/api/upload_scene")
async def upload_scene(file: UploadFile = File(...)):
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "scene.usda").suffix
    if suffix.lower() not in {".usd", ".usda", ".usdc"}:
        raise HTTPException(status_code=400, detail="Expected a .usd/.usda/.usdc file")
    dest = UPLOADS_DIR / (Path(file.filename).name)
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
    except Exception as exc:
        logger.exception("Failed to save uploaded scene")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"path": str(dest.resolve())}


@app.get("/api/selected")
async def get_selected():
    return {"selected": viewer.selected_path}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info("Client connected (%d total)", len(connected_clients))
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            await handle_command(websocket, data)
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
    finally:
        connected_clients.discard(websocket)


async def handle_command(client: WebSocket, data: dict) -> None:
    cmd = data.get("cmd")
    try:
        if cmd == "load":
            path = data.get("path", DEFAULT_SCENE)
            await asyncio.to_thread(
                viewer.load_scene,
                path,
                data.get("render_product"),
                data.get("camera_path"),
            )
            await send_json(
                client,
                {
                    "ok": True,
                    "cmd": cmd,
                    "scene": path,
                    "render_product": viewer.render_product,
                    "camera_path": viewer.camera_path,
                },
            )

        elif cmd == "pick":
            x, y = float(data["x"]), float(data["y"])
            path = await asyncio.to_thread(viewer.pick, x, y)
            await send_json(
                client, {"ok": True, "cmd": cmd, "path": path, "x": x, "y": y}
            )

        elif cmd == "select":
            path = data.get("path")
            await asyncio.to_thread(viewer.select, path)
            await send_json(client, {"ok": True, "cmd": cmd, "selected": path})

        elif cmd == "translate":
            target = data.get("path", viewer.selected_path)
            if not target:
                raise ValueError("No prim selected or specified")
            await asyncio.to_thread(
                viewer.translate,
                target,
                float(data.get("dx", 0)),
                float(data.get("dy", 0)),
                float(data.get("dz", 0)),
            )
            await send_json(client, {"ok": True, "cmd": cmd, "path": target})

        elif cmd == "rotate":
            target = data.get("path", viewer.selected_path)
            if not target:
                raise ValueError("No prim selected or specified")
            await asyncio.to_thread(
                viewer.rotate,
                target,
                data.get("axis", "y"),
                float(data.get("degrees", 10)),
            )
            await send_json(client, {"ok": True, "cmd": cmd, "path": target})

        elif cmd == "scale":
            target = data.get("path", viewer.selected_path)
            if not target:
                raise ValueError("No prim selected or specified")
            await asyncio.to_thread(
                viewer.scale,
                target,
                float(data.get("sx", 1.0)),
                float(data.get("sy", 1.0)),
                float(data.get("sz", 1.0)),
            )
            await send_json(client, {"ok": True, "cmd": cmd, "path": target})

        elif cmd == "camera":
            await asyncio.to_thread(
                viewer.translate_camera,
                float(data.get("dx", 0)),
                float(data.get("dy", 0)),
                float(data.get("dz", 0)),
            )
            await send_json(client, {"ok": True, "cmd": cmd})

        elif cmd == "list_prims":
            prims = await asyncio.to_thread(viewer.query_prims)
            await send_json(
                client, {"ok": True, "cmd": cmd, "prims": list(prims.keys())}
            )

        else:
            await send_json(client, {"ok": False, "error": f"Unknown cmd: {cmd}"})
    except Exception as exc:
        logger.exception("Command failed: %s", data)
        await send_json(client, {"ok": False, "cmd": cmd, "error": str(exc)})


def main():
    uvicorn.run("rtx_viewer.server:app", host="0.0.0.0", port=8080, reload=False)


if __name__ == "__main__":
    main()
