"""
dynamic_render_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~

Utility helpers to run dynamically supplied PyVista snippets that output a
headless screenshot.  Two execution modes are provided:

- run_with_exec:        runs the snippet in-process via exec().
- run_with_process_pool: runs the snippet in a worker process via ProcessPoolExecutor.

Both helpers return the path to the image file the snippet produced.
"""

from __future__ import annotations

import atexit
import os
import tempfile
import uuid
from concurrent.futures import Future, ProcessPoolExecutor
from pathlib import Path
from typing import Dict, Optional

import pyvista as pv

# ---------------------------------------------------------------------------
# Global PyVista configuration (headless/off-screen rendering).
# ---------------------------------------------------------------------------

# Ensure PyVista/VTK render off-screen so the code works on headless servers.
os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")
# pv.global_theme.off_screen = True
# pv.global_theme.silence_warnings = True
pv.global_theme.window_size = (1024, 768)

# Try to start an X virtual framebuffer if available (mostly useful on Linux).
try:
    pv.start_xvfb()
except Exception:
    pass  # Not fatal; off-screen rendering will still work without XVFB on most setups.

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_output_path(output_path: Optional[Path]) -> Path:
    """Create parent directories and return an absolute output path."""
    if output_path is None:
        output_path = Path(tempfile.gettempdir()) / f"pyvista_{uuid.uuid4().hex}.png"

    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def _build_exec_namespace(
    output_path: Path, extra_globals: Optional[Dict[str, object]] = None
) -> Dict[str, object]:
    """
    Build the namespace exposed to the dynamic snippet.

    Anything you inject here becomes directly visible to the user code.
    """
    namespace: Dict[str, object] = {
        "__builtins__": __builtins__,
        "__name__": "__dynamic_pyvista__",  # stops weird module-related checks in some libraries
        "pv": pv,
        # We give the snippet a well-known variable so it knows where to save the screenshot.
        "OUTPUT_PATH": str(output_path),
    }

    if extra_globals:
        namespace.update(extra_globals)

    return namespace


def _assert_image_exists(path: Path) -> Path:
    if not path.exists():
        raise RuntimeError(
            f"The dynamic snippet finished but no image was written at {path}.\n"
            "Make sure the user code calls plotter.show(screenshot=OUTPUT_PATH, auto_close=True)."
        )
    return path


# ---------------------------------------------------------------------------
# In‑process execution using exec()
# ---------------------------------------------------------------------------


def run_with_exec(
    code: str,
    *,
    output_path: Optional[str | Path] = None,
    extra_globals: Optional[Dict[str, object]] = None,
) -> Path:
    """
    Execute `code` in-process via exec() and return the screenshot path.

    Parameters
    ----------
    code:
        Python source supplied by the caller.  The code must eventually write an
        image to OUTPUT_PATH (e.g., call `plotter.show(screenshot=OUTPUT_PATH, auto_close=True)`).
    output_path:
        Optional explicit destination for the screenshot.  A temporary file is used otherwise.
    extra_globals:
        Optional dict of additional symbols to expose to the snippet.
    """
    output_path = _ensure_output_path(Path(output_path) if output_path else None)
    namespace = _build_exec_namespace(output_path, extra_globals)

    compiled = compile(code, "<dynamic-pyvista>", "exec")
    exec(compiled, namespace, namespace)

    return _assert_image_exists(output_path)


# ---------------------------------------------------------------------------
# ProcessPoolExecutor execution
# ---------------------------------------------------------------------------

_process_pool: Optional[ProcessPoolExecutor] = None


def _get_pool() -> ProcessPoolExecutor:
    global _process_pool
    if _process_pool is None:
        # Limit max_workers if you want better control (e.g., CPU-bound workloads).
        _process_pool = ProcessPoolExecutor()
    return _process_pool


def _worker(code: str, output_path: str, extra_globals: Dict[str, object]) -> str:
    """
    Worker routine executed inside each process.  It configures PyVista
    off-screen rendering again because each process has its own interpreter.
    """
    import pyvista as _pv
    import os as _os

    _os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")
    # _pv.global_theme.off_screen = True
    # _pv.global_theme.silence_warnings = True
    _pv.global_theme.window_size = (1024, 768)

    try:
        _pv.start_xvfb()
    except Exception:
        pass

    namespace = {
        "__builtins__": __builtins__,
        "__name__": "__dynamic_pyvista_worker__",
        "pv": _pv,
        "OUTPUT_PATH": output_path,
    }
    if extra_globals:
        namespace.update(extra_globals)

    compiled = compile(code, "<dynamic-pyvista-worker>", "exec")
    exec(compiled, namespace, namespace)

    # Return path as string (ProcessPoolExecutor needs picklable objects)
    return output_path


def run_with_process_pool(
    code: str,
    *,
    output_path: Optional[str | Path] = None,
    extra_globals: Optional[Dict[str, object]] = None,
) -> Path:
    """
    Execute `code` inside a worker process and return the screenshot path.

    Parameters are identical to run_with_exec.
    """
    output_path = _ensure_output_path(Path(output_path) if output_path else None)
    pool = _get_pool()

    future: Future[str] = pool.submit(
        _worker, code, str(output_path), extra_globals or {}
    )
    result_path = Path(future.result())
    return _assert_image_exists(result_path)


@atexit.register
# para FastAPI, chamar em @app.on_event("shutdown")
def _shutdown_pool() -> None:
    """Ensure the ProcessPoolExecutor is cleanly shut down on interpreter exit."""
    if _process_pool:
        _process_pool.shutdown(wait=True)


if __name__ == "__main__":
    code = """
plotter = pv.Plotter(off_screen=True)
plotter.set_background("white")

cubes = [
    (pv.Cube(center=(0.5, 0.5, 0.5)), "#6D8864"),
    (pv.Cube(center=(1.5, 0.5, 0.5)), "#7A6564"),
    (pv.Cube(center=(2.5, 0.5, 0.5)), "#6C8CA3"),
    (pv.Cube(center=(0.5, 0.5, 1.5)), "#6D887B"),
    (pv.Cube(center=(0.5, -0.5, 0.5)), "#B59675"),
]

for geom, color in cubes:
    plotter.add_mesh(geom, color=color, show_edges=True, edge_color="black")

plotter.reset_camera()
plotter.camera_position = [
    (1.0, 0.0, 10.0),
    (1.0, 0.0, 0.5),
    (0, 1, 0),
]
plotter.camera.zoom(1.2)
plotter.show_grid()

# IMPORTANT: write to OUTPUT_PATH.  Without this, the server raises an error.
plotter.show(screenshot=OUTPUT_PATH, auto_close=True)


"""

    strategy = "exec-xx"
    if strategy == "exec":
        image_path = run_with_exec(code)  # é mais rápido..
    else:
        image_path = run_with_process_pool(code)
    print(f"path={image_path} media_type=image/png filename={image_path.name}")
