"""Filesystem directories used by ``StaticFiles`` mounts in ``app/web/main.py``."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_SPATIALVIZ_PROBLEMS = _REPO_ROOT / "data" / "spatialviz" / "problems"

DATASET_EVAL_IMAGES_DIR = (
    _DATA_SPATIALVIZ_PROBLEMS
    / "dataset-eval2-1001--3d-rotation-level-0"
    / "images"
)
PROBLEMS_IMAGES_DIR = _DATA_SPATIALVIZ_PROBLEMS / "images"
SLICES_IMAGES_DIR = _REPO_ROOT / "data"  / "spatialviz-3d-slices" / "data"

MOUNT_DATASET_EVAL_IMAGES = "/dataset-eval2-1001--3d-rotation-level-0/images"
MOUNT_PROBLEMS_IMAGES = "/problems/images"

# slice images
MOUNT_SLICES = "/spatialviz-3d-slices/data"
SLICES_IMAGES_DIR = _REPO_ROOT / "data"  / "spatialviz-3d-slices" / "data"
