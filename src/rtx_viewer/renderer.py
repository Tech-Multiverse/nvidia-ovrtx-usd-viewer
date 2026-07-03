"""Thread-safe ovrtx renderer wrapper for the RTX viewer."""

import io
import logging
import math
import threading
from typing import Optional

import numpy as np
import ovrtx
from PIL import Image

logger = logging.getLogger(__name__)


class RTXViewerRenderer:
    """Wraps ovrtx.Renderer to provide frame streaming, picking, and editing."""

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        render_product: Optional[str] = None,
        camera_path: Optional[str] = None,
    ):
        self.width = width
        self.height = height
        self.render_product = render_product
        self.camera_path = camera_path
        self.selected_path: Optional[str] = None
        self.has_scene = False
        self._lock = threading.Lock()

        config = ovrtx.RendererConfig(
            selection_outline_enabled=True,
            log_file_path="ovrtx-viewer.log",
        )
        self._renderer = ovrtx.Renderer(config=config)
        logger.info("ovrtx renderer created")

    def _discover_paths(self) -> None:
        """Pick the first render product and camera if not already set."""
        if not self.render_product:
            products = self._renderer.query_prims(
                require_all=[(ovrtx.FilterKind.PRIM_TYPE, "RenderProduct")],
                attribute_filter_mode=ovrtx.AttributeFilterMode.NONE,
            )
            if products:
                self.render_product = next(iter(products))
                logger.info("Discovered render product: %s", self.render_product)
            else:
                logger.warning("No RenderProduct found in scene")

        if not self.camera_path:
            cameras = self._renderer.query_prims(
                require_all=[(ovrtx.FilterKind.PRIM_TYPE, "Camera")],
                attribute_filter_mode=ovrtx.AttributeFilterMode.NONE,
            )
            if cameras:
                self.camera_path = self._pick_main_camera(cameras)
                logger.info("Discovered camera: %s", self.camera_path)
            else:
                logger.warning("No Camera found in scene")

    @staticmethod
    def _pick_main_camera(cameras: dict) -> str:
        """Prefer a simple camera name over debug/test cameras."""
        paths = list(cameras.keys())
        for path in paths:
            name = path.split("/")[-1].lower()
            if name in {"camera", "camera0", "cam"}:
                return path
        for path in paths:
            name = path.split("/")[-1].lower()
            if "motion" not in name and "test" not in name:
                return path
        return paths[0]

    def load_scene(
        self,
        usd_path: str,
        render_product: Optional[str] = None,
        camera_path: Optional[str] = None,
    ) -> None:
        with self._lock:
            self.render_product = render_product
            self.camera_path = camera_path
            self._renderer.open_usd(usd_path)
            self._renderer.reset()
            self._discover_paths()
            # Quick warm-up so the first streamed frame is not black.
            if self.render_product:
                for _ in range(2):
                    self._renderer.step(
                        render_products={self.render_product},
                        delta_time=1.0 / 60.0,
                    )
            self.selected_path = None
            self.has_scene = bool(self.render_product)
            if not self.has_scene:
                logger.error("No render product found; scene not ready to render")
        logger.info("Loaded scene: %s", usd_path)

    def query_prims(self) -> dict:
        with self._lock:
            return self._renderer.query_prims(
                attribute_filter_mode=ovrtx.AttributeFilterMode.NONE
            )

    def render_frame_jpeg(self) -> bytes:
        """Render one frame and return it as JPEG bytes."""
        with self._lock:
            products = self._renderer.step(
                render_products={self.render_product},
                delta_time=1.0 / 60.0,
            )
            frame = products[self.render_product].frames[0]
            mapping = frame.render_vars["LdrColor"].map(device=ovrtx.Device.CPU)
            pixels = np.from_dlpack(mapping)

        # pixels is HxWxRGBA uint8. Resize if requested and encode.
        img = Image.fromarray(pixels).convert("RGB")
        if img.size != (self.width, self.height):
            img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    def pick(self, nx: float, ny: float) -> Optional[str]:
        """Pick the prim at normalized screen coordinates (0..1, 0..1)."""
        x = int(nx * self.width)
        y = int(ny * self.height)
        with self._lock:
            self._renderer.enqueue_pick_query(
                render_product_path=self.render_product,
                left=x,
                top=y,
                right=x + 1,
                bottom=y + 1,
            )
            products = self._renderer.step(
                render_products={self.render_product},
                delta_time=1.0 / 60.0,
            )
            frame = products[self.render_product].frames[0]
            pick_var = frame.render_vars[ovrtx.OVRTX_RENDER_VAR_PICK_HIT]
            mapping = pick_var.map(device=ovrtx.Device.CPU)

            hit_count = int(
                np.from_dlpack(mapping.params["hitCount"]).reshape(-1)[0]
            )
            if hit_count == 0:
                mapping.unmap()
                return None

            prim_paths = np.from_dlpack(mapping["primPath"]).copy().reshape(-1)
            path_id = int(prim_paths[0])
            mapping.unmap()
            path = self._renderer.resolve_prim_path_id(path_id)
            if path == "":
                return None
            return path

    def select(self, prim_path: Optional[str]) -> None:
        """Highlight the given prim with the selection outline."""
        with self._lock:
            if self.selected_path:
                self._renderer.write_attribute(
                    prim_paths=[self.selected_path],
                    attribute_name=ovrtx.OVRTX_ATTR_NAME_SELECTION_OUTLINE_GROUP,
                    tensor=np.array([0], dtype=np.uint8),
                )
            self.selected_path = prim_path
            if prim_path:
                self._renderer.write_attribute(
                    prim_paths=[prim_path],
                    attribute_name=ovrtx.OVRTX_ATTR_NAME_SELECTION_OUTLINE_GROUP,
                    tensor=np.array([1], dtype=np.uint8),
                )
        logger.info("Selected: %s", prim_path)

    def _get_xform(self, prim_path: str) -> np.ndarray:
        tensor = self._renderer.read_attribute("omni:xform", [prim_path])
        return np.from_dlpack(tensor).reshape(1, 4, 4).copy()

    def _set_xform(self, prim_path: str, matrix: np.ndarray) -> None:
        self._renderer.write_attribute(
            prim_paths=[prim_path],
            attribute_name="omni:xform",
            tensor=matrix,
        )

    def translate(self, prim_path: str, dx: float, dy: float, dz: float) -> None:
        with self._lock:
            matrix = self._get_xform(prim_path)
            matrix[0, 3, 0] += dx
            matrix[0, 3, 1] += dy
            matrix[0, 3, 2] += dz
            self._set_xform(prim_path, matrix)
        logger.info("Translated %s by (%g, %g, %g)", prim_path, dx, dy, dz)

    def rotate(self, prim_path: str, axis: str, degrees: float) -> None:
        """Rotate the prim around a local axis (x, y, or z)."""
        with self._lock:
            matrix = self._get_xform(prim_path)[0]
            radians = math.radians(degrees)
            c, s = math.cos(radians), math.sin(radians)
            if axis == "x":
                rot = np.array(
                    [[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]],
                    dtype=np.float64,
                )
            elif axis == "y":
                rot = np.array(
                    [[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]],
                    dtype=np.float64,
                )
            elif axis == "z":
                rot = np.array(
                    [[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                    dtype=np.float64,
                )
            else:
                raise ValueError(f"Invalid axis: {axis}")
            matrix = rot @ matrix
            self._set_xform(prim_path, matrix.reshape(1, 4, 4))
        logger.info("Rotated %s around %s by %g deg", prim_path, axis, degrees)

    def scale(self, prim_path: str, sx: float, sy: float, sz: float) -> None:
        """Scale the prim uniformly or per-axis."""
        with self._lock:
            matrix = self._get_xform(prim_path)[0]
            scale = np.diag([sx, sy, sz, 1.0])
            matrix = scale @ matrix
            self._set_xform(prim_path, matrix.reshape(1, 4, 4))
        logger.info("Scaled %s by (%g, %g, %g)", prim_path, sx, sy, sz)

    def translate_camera(self, dx: float, dy: float, dz: float) -> None:
        self.translate(self.camera_path, dx, dy, dz)

    def close(self) -> None:
        with self._lock:
            del self._renderer
        logger.info("Renderer closed")
