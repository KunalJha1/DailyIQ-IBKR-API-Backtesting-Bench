from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_ID = "com.dailyiq.app"


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


def _default_app_data_dir() -> Path | None:
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / APP_ID

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / APP_ID
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_ID
    return home / ".local" / "share" / APP_ID


def data_dir() -> Path:
    override = os.environ.get("DAILYIQ_DATA_DIR")
    if override:
        return Path(override).expanduser()
    app_data = _default_app_data_dir()
    if app_data:
        return app_data
    return PROJECT_ROOT / "data"
