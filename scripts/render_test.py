"""Standalone test that renders a built-in ovrtx scene to a PNG."""
import numpy as np
import ovrtx
from pathlib import Path
from PIL import Image

# Use the ovrtx test scene included in the package.
DATA_DIR = Path(ovrtx.__file__).parent / "tests" / "data"
TEST_SCENE = DATA_DIR / "simple_scene.usda"
OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

print(f"Loading scene: {TEST_SCENE}")
config = ovrtx.RendererConfig(log_file_path=str(OUTPUT_DIR / "render_test.ovrtx.log"))
renderer = ovrtx.Renderer(config=config)
renderer.open_usd(str(TEST_SCENE))
renderer.reset()

# Discover the first render product and camera.
products = renderer.query_prims(
    require_all=[(ovrtx.FilterKind.PRIM_TYPE, "RenderProduct")],
    attribute_filter_mode=ovrtx.AttributeFilterMode.NONE,
)
render_product = next(iter(products)) if products else None
print(f"Discovered render product: {render_product}")

cameras = renderer.query_prims(
    require_all=[(ovrtx.FilterKind.PRIM_TYPE, "Camera")],
    attribute_filter_mode=ovrtx.AttributeFilterMode.NONE,
)
camera_path = next(iter(cameras)) if cameras else None
print(f"Discovered camera: {camera_path}")

print("Warming up...")
for _ in range(5):
    renderer.step(render_products={render_product}, delta_time=1.0 / 60)

print("Rendering frame...")
products = renderer.step(render_products={render_product}, delta_time=1.0 / 60)

for product in products.values():
    for frame in product.frames:
        var = frame.render_vars["LdrColor"].map(device=ovrtx.Device.CPU)
        pixels = np.from_dlpack(var)
        print(f"Rendered shape={pixels.shape}, dtype={pixels.dtype}")
        img = Image.fromarray(pixels)
        out_path = OUTPUT_DIR / "render_test.png"
        img.save(out_path)
        print(f"Saved to {out_path}")

del renderer
print("Done")
