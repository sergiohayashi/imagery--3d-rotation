from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

# api/app/config -> parents[2] is api/; parents[3] is repo root (sibling of data/)
_REPO_ROOT = Path(__file__).resolve().parents[3]

# HTTP path for StaticFiles mount of ``local_files_root_dir`` (keep in sync with app/web/main.py).
LOCAL_FILES_MOUNT_PREFIX = "/local-bucket"


@dataclass
class CLIConfig:
    reasoning_model: str | None = None


@dataclass
class GlobalConfig:
    use_local_files: bool = True
    cli: CLIConfig = field(default_factory=CLIConfig)


    @cached_property
    def data_root_dir(self) -> Path:
        return (_REPO_ROOT / "data").resolve()

    @cached_property
    def local_files_root_dir(self) -> str:
        # Same as ../data/__local_bucket when cwd is the api/ folder; resolved from this file.
        root = (_REPO_ROOT / "data" / "__local_bucket__").resolve()
        if not root.is_dir():
            root.mkdir(parents=True, exist_ok=True)
        print(f"[global_config] local_files_root_dir: {root}")
        return str(root)


the_global_config = GlobalConfig()
# First access: mkdir (if needed) + log (once per process)
_ = the_global_config.local_files_root_dir
