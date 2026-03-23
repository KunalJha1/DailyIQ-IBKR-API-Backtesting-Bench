from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def resource_path(*parts: str) -> Path:
    return bundle_root().joinpath(*parts)


def data_dir() -> Path:
    override = os.environ.get("DAILYIQ_DATA_DIR")
    if override:
        return Path(override).expanduser()
    return PROJECT_ROOT / "data"
