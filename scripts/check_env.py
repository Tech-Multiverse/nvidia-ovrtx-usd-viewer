"""Check that all runtime dependencies (Omniverse + web stack) are importable."""
import sys
import importlib


def check(name):
    try:
        m = importlib.import_module(name)
        ver = getattr(m, "__version__", "unknown")
        return f"OK    {name:30s} {ver}"
    except Exception as e:
        return f"FAIL  {name:30s} {type(e).__name__}: {e}"

modules = [
    "ovrtx", "omni.usd", "carb", "pxr", "omni.kit.app",
    "omni.kit.renderer_rtx", "omni.kit.viewport", "omni.kit.streamsdk",
    "omni.physx", "fastapi", "uvicorn", "websockets", "numpy", "PIL",
]

print(f"Python: {sys.executable}")
print(f"Version: {sys.version}")
for m in modules:
    print(check(m))
