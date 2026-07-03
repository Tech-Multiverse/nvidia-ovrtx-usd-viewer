"""Test the RTXViewerRenderer wrapper directly: load, render, and pick."""
import asyncio
from pathlib import Path

import ovrtx
from rtx_viewer.renderer import RTXViewerRenderer


async def main():
    scene = str(Path(ovrtx.__file__).parent / "tests" / "data" / "simple_scene.usda")
    r = RTXViewerRenderer(width=640, height=360)
    r.load_scene(scene)
    print(f"Loaded scene: {scene}")
    print(f"Render product: {r.render_product}")
    print(f"Camera: {r.camera_path}")
    frame = await asyncio.to_thread(r.render_frame_jpeg)
    print(f"Rendered frame: {len(frame)} bytes")
    path = await asyncio.to_thread(r.pick, 0.5, 0.5)
    print(f"Pick at center: {path}")
    r.close()


asyncio.run(main())
