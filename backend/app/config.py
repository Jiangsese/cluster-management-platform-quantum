from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "量子 集群/服务器控制台"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = int(os.environ.get("CLUSTER_PANEL_PORT", "8710"))

DEFAULT_BASTION_HOST = os.environ.get("CLUSTER_PANEL_BASTION_HOST", "")
DEFAULT_BASTION_PORT = int(os.environ.get("CLUSTER_PANEL_BASTION_PORT", "22"))
DEFAULT_INNER_HOST = os.environ.get("CLUSTER_PANEL_INNER_HOST", "")
DEFAULT_INNER_PORT = int(os.environ.get("CLUSTER_PANEL_INNER_PORT", "22"))


def _bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[2]


def _runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


BASE_DIR = _bundle_dir()
RUNTIME_DIR = _runtime_dir()
FRONTEND_DIR = BASE_DIR / "frontend" / "static"
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = Path(os.environ.get("CLUSTER_PANEL_DATA", str(RUNTIME_DIR / "data")))
DB_PATH = DATA_DIR / "cluster_panel.sqlite3"
DEFAULT_KEY_PATH = Path(os.environ.get("CLUSTER_PANEL_KEY", str(Path.home() / ".ssh" / "cluster_rsa")))
