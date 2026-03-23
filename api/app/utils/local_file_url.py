"""Map ``file://`` URLs to HTTP paths for ``StaticFiles`` mounts (see ``app/web/main.py``)."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from app.config.global_config import LOCAL_FILES_MOUNT_PREFIX, the_global_config
from app.config.static_mounts import (
    DATASET_EVAL_IMAGES_DIR,
    MOUNT_DATASET_EVAL_IMAGES,
    MOUNT_PROBLEMS_IMAGES,
    PROBLEMS_IMAGES_DIR,
)


# def _api_public_base_url() -> str:
#     """Strip trailing slash. When the SPA runs on another origin (e.g. :3000), set API_PUBLIC_BASE_URL to the API origin (e.g. http://localhost:8000)."""
#     return os.getenv("API_PUBLIC_BASE_URL", "").strip().rstrip("/")


# def _with_public_base(path_only: str) -> str:
#     base = _api_public_base_url()
#     if base:
#         return f"{base}{path_only}"
#     return path_only


def _mount_pairs() -> list[tuple[str, Path]]:
    """
    (URL prefix, directory root) for each StaticFiles mount.
    Sorted with the deepest directory first so a nested layout wins if paths ever overlap.
    """
    local_root = Path(the_global_config.local_files_root_dir).resolve()
    pairs = [
        (MOUNT_DATASET_EVAL_IMAGES, DATASET_EVAL_IMAGES_DIR.resolve()),
        (MOUNT_PROBLEMS_IMAGES, PROBLEMS_IMAGES_DIR.resolve()),
        (LOCAL_FILES_MOUNT_PREFIX, local_root),
    ]
    return sorted(pairs, key=lambda x: len(x[1].parts), reverse=True)


def file_url_to_mounted_url(file_url: str | None) -> str | None:
    """
    If ``file_url`` is ``file://`` and the path lies under one of the static mount roots
    (dataset eval images, problems images, or ``local_files_root_dir``), return the
    corresponding URL path for that mount.

    If ``API_PUBLIC_BASE_URL`` is set, the result is absolute (e.g. ``http://localhost:8000/problems/images/...``).
    Otherwise returns a root-relative path (same-origin as the page).
    """
    if not file_url or not file_url.startswith("file://"):
        return file_url
    parsed = urlparse(file_url)
    path = unquote(parsed.path)
    if not path and parsed.netloc:
        # Windows: file://C:\path or file://C:/path puts the full path in netloc
        # (urlparse treats everything after // as netloc when there's no forward slash)
        path = unquote(parsed.netloc)
    if not path:
        return file_url
    # Convert URL path to filesystem path (handles /C:/... format on Windows)
    if path.startswith("/"):
        path = url2pathname(path)
    try:
        fs_path = Path(path).resolve()
    except OSError:
        return file_url

    for url_prefix, root_dir in _mount_pairs():
        try:
            rel = fs_path.relative_to(root_dir)
        except ValueError:
            continue
        rel_posix = rel.as_posix()
        prefix = url_prefix.rstrip("/")
        path_only = f"{prefix}/{rel_posix}" if rel_posix else prefix
        return "file://" + path_only  # the full path in handled in the frontned

    return file_url


def rewrite_output_file_urls(output: list | dict | None):
    """Rewrite ``file_url`` fields inside assistant ``output`` items when they are ``file://`` local paths."""
    if not output:
        return output
    if isinstance(output, dict):
        if output.get("file_url"):
            out = dict(output)
            out["file_url"] = file_url_to_mounted_url(output["file_url"])
            return out
        return output
    new_list = []
    for item in output:
        if isinstance(item, dict) and item.get("file_url"):
            d = dict(item)
            d["file_url"] = file_url_to_mounted_url(item["file_url"])
            new_list.append(d)
        else:
            new_list.append(item)
    return new_list


# print mount_pairs
print( "--------------------------------------\nmount_pairs:\n--------------------------------------")
for pair in _mount_pairs():
    print(f"URL prefix: {pair[0]}, directory root: {pair[1]}")
print( "--------------------------------------\n--------------------------------------")