from __future__ import annotations

import base64
import ctypes
import json
import sys
import math
import os
import posixpath
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, QPointF, QRunnable, QRectF, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor, QBrush, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from backend.app.config import (
    APP_NAME,
    ASSETS_DIR,
    DATA_DIR,
    DEFAULT_BASTION_HOST,
    DEFAULT_BASTION_PORT,
    DEFAULT_INNER_HOST,
    DEFAULT_INNER_PORT,
    DEFAULT_KEY_PATH,
)
from backend.app.remote import (
    delete_path,
    download_file_stream,
    get_dashboard,
    get_login_health,
    get_job_logs,
    kill_process,
    list_files,
    mkdir_path,
    read_text_file,
    rename_path,
    run_shell_command,
    stop_job,
    submit_job,
    upload_file,
)
from backend.app.sessions import ClusterCredentials
from backend.app.ssh_client import ClusterSSHError


STYLE = """
QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 13px;
    color: #1d1d1f;
    background: transparent;
}
QDialog, QMainWindow {
    background: #060a13;
}
QDialog#LoginDialog {
    background: transparent;
}
QLabel {
    background: transparent;
}
QLabel#Title {
    font-size: 32px;
    font-weight: 750;
    color: #05070b;
}
QLabel#MainTitle {
    font-size: 30px;
    font-weight: 760;
    color: #f7faff;
}
QLabel#Subtitle {
    color: #555f70;
    font-size: 13px;
}
QLabel#InlineStatus {
    color: rgba(17, 24, 39, 220);
    font-size: 12px;
    font-weight: 560;
}
QLabel#MainSubtitle {
    color: rgba(238, 244, 255, 215);
    font-size: 13px;
}
QLabel#FieldLabel {
    color: #202734;
    font-size: 14px;
    font-weight: 650;
    background: transparent;
}
QLabel#SectionTitle {
    color: #111827;
    font-size: 16px;
    font-weight: 750;
    background: transparent;
}
QLabel#BrandBadge {
    background: transparent;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 800;
}
QFrame#Panel, QGroupBox {
    background: rgba(246, 249, 253, 218);
    border: 1px solid rgba(255, 255, 255, 156);
    border-radius: 8px;
}
QFrame#LoginCard {
    background: transparent;
    border: 0;
    border-radius: 8px;
}
QFrame#SettingsPanel {
    background: rgba(247, 250, 255, 108);
    border: 1px solid rgba(228, 234, 244, 146);
    border-radius: 7px;
}
QGroupBox {
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #30343b;
}
QLineEdit, QTextEdit, QPlainTextEdit {
    background: rgba(255, 255, 255, 172);
    border: 1px solid rgba(220, 228, 240, 150);
    border-radius: 6px;
    padding: 9px 11px;
    selection-background-color: #344054;
    min-height: 24px;
    font-size: 14px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #5c6f8a;
    background: rgba(255, 255, 255, 205);
}
QLineEdit#CompactInput {
    min-height: 18px;
    padding: 6px 10px;
    background: rgba(255, 255, 255, 132);
}
QLineEdit#CompactInput:focus {
    background: rgba(255, 255, 255, 168);
}
QLineEdit#JobInput {
    min-height: 18px;
    padding: 6px 11px;
}
QLineEdit#JobInput:focus {
    background: rgba(255, 255, 255, 186);
}
QPlainTextEdit#TerminalOutput {
    background: rgba(7, 11, 18, 236);
    color: #e8edf5;
    border: 1px solid rgba(132, 150, 178, 132);
    border-radius: 6px;
    padding: 14px;
    selection-background-color: rgba(69, 113, 177, 180);
    font-family: "Cascadia Mono", "Consolas", "Microsoft YaHei UI";
    font-size: 13px;
}
QLineEdit#TerminalInput {
    background: rgba(8, 13, 22, 232);
    color: #f5f8ff;
    border: 1px solid rgba(132, 150, 178, 150);
    border-radius: 6px;
    padding: 9px 12px;
    selection-background-color: rgba(69, 113, 177, 180);
    font-family: "Cascadia Mono", "Consolas", "Microsoft YaHei UI";
    font-size: 13px;
}
QLineEdit#TerminalInput:focus {
    border-color: rgba(142, 201, 255, 210);
    background: rgba(10, 16, 28, 242);
}
QLabel#TerminalPrompt {
    color: #d9e6ff;
    font-family: "Cascadia Mono", "Consolas", "Microsoft YaHei UI";
    font-size: 13px;
    font-weight: 650;
}
QComboBox {
    background: rgba(255, 255, 255, 146);
    border: 1px solid rgba(221, 228, 238, 132);
    border-radius: 6px;
    padding: 8px 10px;
    min-height: 24px;
    font-size: 14px;
    selection-background-color: rgba(205, 220, 245, 180);
}
QComboBox:hover {
    background: rgba(255, 255, 255, 178);
    border-color: rgba(152, 166, 188, 200);
}
QComboBox:focus {
    border-color: #566070;
    background: rgba(255, 255, 255, 190);
}
QComboBox:disabled {
    color: #98a2b3;
    background: rgba(245, 247, 250, 126);
}
QComboBox QAbstractItemView {
    background: rgba(250, 252, 255, 245);
    color: #1d1d1f;
    border: 1px solid rgba(215, 222, 235, 220);
    selection-background-color: rgba(214, 229, 250, 230);
    outline: 0;
}
QCheckBox {
    background: transparent;
    color: #4a5565;
    spacing: 8px;
}
QPushButton {
    background: rgba(247, 250, 255, 202);
    border: 1px solid rgba(218, 226, 238, 190);
    border-radius: 6px;
    min-height: 34px;
    padding: 7px 14px;
    font-weight: 650;
    font-size: 14px;
}
QPushButton:hover {
    background: rgba(255, 255, 255, 236);
    border-color: rgba(139, 158, 184, 220);
    color: #0f172a;
}
QPushButton:pressed {
    background: rgba(220, 229, 242, 238);
    border-color: rgba(93, 111, 138, 225);
    padding-top: 8px;
    padding-bottom: 6px;
}
QPushButton:disabled {
    color: #98a2b3;
    background: rgba(245, 247, 250, 150);
    border-color: rgba(226, 232, 240, 150);
}
QPushButton#Primary {
    background: #101827;
    color: #ffffff;
    border-color: rgba(255, 255, 255, 42);
    min-height: 44px;
    padding: 0px 14px;
    font-size: 14px;
}
QPushButton#Primary:hover {
    background: #1e2b3d;
    border-color: rgba(255, 255, 255, 80);
}
QPushButton#Primary:pressed {
    background: #0b1220;
    border-color: rgba(142, 201, 255, 120);
    padding: 1px 14px 0px 14px;
}
QPushButton#SubmitJob {
    background: #111827;
    color: #ffffff;
    border-color: rgba(255, 255, 255, 42);
    min-height: 42px;
    padding: 0px 14px;
    font-size: 14px;
}
QPushButton#SubmitJob:hover {
    background: #253044;
    border-color: rgba(255, 255, 255, 80);
}
QPushButton#SubmitJob:pressed {
    background: #0b1220;
    border-color: rgba(142, 201, 255, 120);
    padding: 1px 14px 0px 14px;
}
QMessageBox {
    background: #111827;
    color: #f8fafc;
}
QMessageBox QLabel {
    color: #f8fafc;
    font-size: 14px;
    background: transparent;
}
QMessageBox QPushButton {
    background: rgba(255, 255, 255, 235);
    color: #111827;
    border: 1px solid rgba(203, 213, 225, 220);
    border-radius: 6px;
    min-width: 76px;
    min-height: 32px;
    padding: 5px 14px;
}
QMessageBox QPushButton:hover {
    background: #ffffff;
    border-color: rgba(142, 201, 255, 220);
}
QMessageBox QPushButton:pressed {
    background: #dbe5f4;
    padding-top: 6px;
    padding-bottom: 4px;
}
QPushButton#Ghost {
    background: rgba(247, 250, 255, 132);
    color: #30343b;
    border-color: rgba(214, 220, 228, 160);
    min-height: 30px;
}
QPushButton#Ghost:hover {
    background: rgba(255, 255, 255, 202);
    border-color: rgba(152, 166, 188, 220);
}
QPushButton#Ghost:pressed {
    background: rgba(224, 231, 241, 215);
    border-color: rgba(104, 119, 142, 220);
}
QPushButton#ModeToggle {
    background: rgba(255, 255, 255, 112);
    color: #3d4654;
    border-color: rgba(218, 224, 234, 160);
    min-height: 32px;
    padding: 6px 12px;
}
QPushButton#ModeToggle:hover {
    background: rgba(255, 255, 255, 176);
    border-color: rgba(152, 166, 188, 210);
}
QPushButton#ModeToggle:checked {
    background: rgba(244, 248, 255, 226);
    color: #111827;
    border-color: rgba(142, 201, 255, 210);
}
QPushButton#ModeToggle:pressed {
    background: rgba(224, 231, 241, 224);
    padding-top: 7px;
    padding-bottom: 5px;
}
QPushButton#Danger {
    color: #b42318;
    background: #fff7f6;
    border-color: #f3c7c2;
}
QPushButton#Danger:hover {
    color: #912018;
    background: #ffebe8;
    border-color: #eda8a0;
}
QPushButton#Danger:pressed {
    color: #7a1a13;
    background: #ffe1dd;
    border-color: #d97065;
}
QPushButton#ProfileAction {
    background: rgba(255, 255, 255, 128);
    color: #30343b;
    border-color: rgba(214, 220, 228, 170);
    min-height: 30px;
    padding: 0px 12px;
}
QPushButton#ProfileAction:hover {
    background: rgba(255, 255, 255, 194);
    border-color: rgba(152, 166, 188, 220);
}
QPushButton#ProfileAction:pressed {
    background: rgba(224, 231, 241, 220);
    border-color: rgba(104, 119, 142, 220);
    padding: 1px 12px 0px 12px;
}
QPushButton#ProfileDanger {
    color: #b42318;
    background: rgba(255, 247, 246, 210);
    border-color: rgba(243, 199, 194, 210);
    min-height: 30px;
    padding: 0px 12px;
}
QPushButton#ProfileDanger:hover {
    color: #912018;
    background: rgba(255, 235, 232, 230);
    border-color: rgba(237, 168, 160, 230);
}
QPushButton#ProfileDanger:pressed {
    color: #7a1a13;
    background: rgba(255, 225, 221, 240);
    border-color: rgba(217, 112, 101, 230);
    padding: 1px 12px 0px 12px;
}
QPushButton#TableAction {
    min-height: 24px;
    padding: 2px 9px;
    border-radius: 5px;
    font-size: 13px;
    background: rgba(255, 255, 255, 212);
    border-color: rgba(220, 226, 236, 190);
}
QPushButton#TableAction:hover {
    background: rgba(255, 255, 255, 240);
    border-color: rgba(152, 166, 188, 210);
}
QPushButton#TableAction:pressed {
    background: rgba(224, 231, 241, 235);
    border-color: rgba(104, 119, 142, 220);
    padding-top: 3px;
    padding-bottom: 1px;
}
QPushButton#TableDanger {
    min-height: 24px;
    padding: 2px 9px;
    border-radius: 5px;
    font-size: 13px;
    color: #b42318;
    background: rgba(255, 247, 246, 218);
    border-color: rgba(243, 199, 194, 210);
}
QPushButton#TableDanger:hover {
    background: rgba(255, 235, 232, 230);
    border-color: rgba(237, 168, 160, 230);
}
QPushButton#TableDanger:pressed {
    color: #7a1a13;
    background: rgba(255, 225, 221, 240);
    border-color: rgba(217, 112, 101, 230);
    padding-top: 3px;
    padding-bottom: 1px;
}
QPushButton#TableDanger:disabled {
    color: #98a2b3;
    background: rgba(248, 250, 252, 180);
    border-color: rgba(226, 232, 240, 170);
}
QTabWidget::pane {
    border: 0;
}
QTabBar::tab {
    background: rgba(239, 244, 251, 186);
    border: 1px solid rgba(255, 255, 255, 126);
    padding: 11px 28px;
    margin-right: 8px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 14px;
    color: #2b3445;
}
QTabBar::tab:selected {
    background: rgba(255, 255, 255, 242);
    color: #0f172a;
    border-color: rgba(142, 201, 255, 190);
}
QTabBar::tab:hover {
    background: rgba(255, 255, 255, 220);
    border-color: rgba(170, 187, 210, 190);
}
QTableWidget {
    background: rgba(250, 252, 255, 218);
    border: 1px solid rgba(222, 231, 242, 220);
    border-radius: 6px;
    gridline-color: rgba(226, 232, 240, 190);
    selection-background-color: rgba(191, 219, 254, 140);
    font-size: 13px;
}
QHeaderView::section {
    background: rgba(242, 246, 252, 242);
    color: #526071;
    border: 0;
    border-bottom: 1px solid rgba(218, 225, 235, 205);
    padding: 8px;
    font-weight: 700;
    font-size: 13px;
}
QProgressBar {
    border: 1px solid #e4e7eb;
    border-radius: 4px;
    background: #f2f4f7;
    text-align: center;
    min-height: 8px;
}
QProgressBar::chunk {
    background: #5f6f85;
    border-radius: 3px;
}
"""


@dataclass
class LoginResult:
    credentials: ClusterCredentials
    health: dict


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass
            return
        try:
            self.signals.finished.emit(result)
        except RuntimeError:
            pass


def human_bytes(value: int | float | None) -> str:
    size = float(value or 0)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if abs(size) < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


REMEMBER_FILE = DATA_DIR / "remembered_login.json"
PROFILES_FILE = DATA_DIR / "cluster_profiles.json"
MODE_BASTION = "bastion"
MODE_DIRECT = "direct"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob_from_bytes(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def protect_secret(text: str) -> str:
    data = text.encode("utf-8")
    if os.name != "nt":
        return base64.b64encode(data).decode("ascii")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_blob, _buffer = _blob_from_bytes(data)
    out_blob = _DataBlob()
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    ):
        raise OSError("Unable to protect saved password")
    try:
        protected = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
    return base64.b64encode(protected).decode("ascii")


def unprotect_secret(encoded: str) -> str:
    data = base64.b64decode(encoded.encode("ascii"))
    if os.name != "nt":
        return data.decode("utf-8")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_blob, _buffer = _blob_from_bytes(data)
    out_blob = _DataBlob()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    ):
        raise OSError("Unable to read saved password")
    try:
        plain = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
    return plain.decode("utf-8")


def load_remembered_login() -> dict:
    try:
        data = json.loads(REMEMBER_FILE.read_text(encoding="utf-8"))
        if data.get("password"):
            data["password"] = unprotect_secret(data["password"])
        return data
    except Exception:
        return {}


def save_remembered_login(credentials: ClusterCredentials) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "username": credentials.username,
        "password": protect_secret(credentials.password),
        "bastion_host": credentials.bastion_host,
        "bastion_port": credentials.bastion_port,
        "inner_host": credentials.inner_host,
        "inner_port": credentials.inner_port,
        "use_key": credentials.use_key,
    }
    REMEMBER_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_remembered_login() -> None:
    try:
        REMEMBER_FILE.unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass


def _normalize_connection_mode(value: str | None) -> str:
    return MODE_DIRECT if value == MODE_DIRECT else MODE_BASTION


def _normalize_profile(raw: dict) -> dict:
    mode = _normalize_connection_mode(str(raw.get("mode") or ""))
    profile = {
        "id": str(raw.get("id") or uuid4().hex),
        "name": str(raw.get("name") or "未命名集群"),
        "mode": mode,
        "username": str(raw.get("username") or ""),
        "password": "",
        "bastion_host": str(raw.get("bastion_host") or DEFAULT_BASTION_HOST),
        "bastion_port": int(raw.get("bastion_port") or DEFAULT_BASTION_PORT),
        "inner_host": str(raw.get("inner_host") or DEFAULT_INNER_HOST),
        "inner_port": int(raw.get("inner_port") or DEFAULT_INNER_PORT),
        "use_key": bool(raw.get("use_key", False)),
    }
    if raw.get("password"):
        try:
            profile["password"] = unprotect_secret(str(raw["password"]))
        except Exception:
            profile["password"] = ""
    return profile


def _legacy_profile() -> dict | None:
    data = load_remembered_login()
    if not data:
        return None
    return {
        "id": "legacy-profile",
        "name": "导入的集群",
        "mode": MODE_BASTION,
        "username": str(data.get("username") or ""),
        "password": str(data.get("password") or ""),
        "bastion_host": str(data.get("bastion_host") or DEFAULT_BASTION_HOST),
        "bastion_port": int(data.get("bastion_port") or DEFAULT_BASTION_PORT),
        "inner_host": str(data.get("inner_host") or DEFAULT_INNER_HOST),
        "inner_port": int(data.get("inner_port") or DEFAULT_INNER_PORT),
        "use_key": bool(data.get("use_key", False)),
    }


def load_cluster_profiles() -> dict:
    try:
        payload = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
    except Exception:
        legacy = _legacy_profile()
        return {"last_profile_id": legacy["id"] if legacy else "", "profiles": [legacy] if legacy else []}

    profiles = []
    for raw in payload.get("profiles", []):
        if isinstance(raw, dict):
            try:
                profiles.append(_normalize_profile(raw))
            except Exception:
                continue
    profile_ids = {profile["id"] for profile in profiles}
    last_profile_id = str(payload.get("last_profile_id") or "")
    if last_profile_id not in profile_ids:
        last_profile_id = profiles[0]["id"] if profiles else ""
    return {"last_profile_id": last_profile_id, "profiles": profiles}


def save_cluster_profiles(profiles: list[dict], last_profile_id: str = "") -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stored_profiles = []
    for profile in profiles:
        stored = {
            "id": str(profile.get("id") or uuid4().hex),
            "name": str(profile.get("name") or "未命名集群"),
            "mode": _normalize_connection_mode(str(profile.get("mode") or "")),
            "username": str(profile.get("username") or ""),
            "password": "",
            "bastion_host": str(profile.get("bastion_host") or DEFAULT_BASTION_HOST),
            "bastion_port": int(profile.get("bastion_port") or DEFAULT_BASTION_PORT),
            "inner_host": str(profile.get("inner_host") or DEFAULT_INNER_HOST),
            "inner_port": int(profile.get("inner_port") or DEFAULT_INNER_PORT),
            "use_key": bool(profile.get("use_key", False)),
        }
        if profile.get("password"):
            stored["password"] = protect_secret(str(profile["password"]))
        stored_profiles.append(stored)
    payload = {"version": 2, "last_profile_id": last_profile_id, "profiles": stored_profiles}
    PROFILES_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def remove_legacy_remembered_login() -> None:
    clear_remembered_login()


def format_ts(value) -> str:
    try:
        return datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def format_duration(seconds: float | int | None) -> str:
    total = int(seconds or 0)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days} 天 {hours} 小时"
    if hours:
        return f"{hours} 小时 {minutes} 分钟"
    return f"{minutes} 分钟"


def is_internal_test_job(job: dict) -> bool:
    name = str(job.get("name") or job.get("id") or "").lower()
    command = str(job.get("command") or "").lower()
    return (
        name.startswith("quantum_console_smoke")
        or name.startswith("kill_button_real_test")
        or "quantum-console-smoke" in command
        or "kill-test-start" in command
    )


def status_palette(status: str) -> tuple[str, str]:
    value = status.lower()
    if value in ("running", "submitted"):
        return "#1f5f6f", "#e5f3f6"
    if value == "finished":
        return "#345682", "#e8eef8"
    if value in ("failed", "lost"):
        return "#9f2f24", "#fbebe9"
    if value == "killed":
        return "#8a5a12", "#f7eedf"
    return "#4a5565", "#f2f4f7"


def source_palette(source: str) -> tuple[str, str, str]:
    if source == "external":
        return "外部", "#475467", "#edf0f4"
    return "平台", "#2254a5", "#e8f0ff"


def job_display_name(job: dict) -> str:
    if job.get("source") == "external":
        args = str(job.get("args") or "").strip()
        command = str(job.get("command") or "").strip()
        text = args or command or str(job.get("pid") or "")
        return text if len(text) <= 42 else text[:39] + "..."
    return str(job.get("name") or job.get("id") or "")


def job_cpu_text(job: dict) -> str:
    value = job.get("cpu_cores")
    if value is None or value == "":
        return "-"
    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)


def job_time_text(job: dict) -> str:
    if job.get("source") == "external":
        return str(job.get("elapsed") or "")
    created = str(job.get("created_at") or "")
    return created.replace("T", " ")[:16]


def clone_credentials(credentials: ClusterCredentials) -> ClusterCredentials:
    return ClusterCredentials(
        username=credentials.username,
        password=credentials.password,
        bastion_host=credentials.bastion_host,
        bastion_port=credentials.bastion_port,
        inner_host=credentials.inner_host,
        inner_port=credentials.inner_port,
        direct=credentials.direct,
        key_path=credentials.key_path,
        use_key=credentials.use_key,
    )


def close_credentials_connection(credentials: ClusterCredentials) -> None:
    connection = getattr(credentials, "connection", None)
    if connection is not None:
        try:
            connection.close()
        except Exception:
            pass


def panel() -> QFrame:
    frame = QFrame()
    frame.setObjectName("Panel")
    return frame


def polish_button(button: QPushButton) -> QPushButton:
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def asset_path(name: str) -> Path:
    return ASSETS_DIR / name


def app_icon() -> QIcon:
    icon_file = asset_path("quantum-icon.png")
    if icon_file.exists():
        return QIcon(str(icon_file))
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#111317"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(8, 8, 48, 48, 9, 9)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "HPC")
    painter.end()
    return QIcon(pixmap)


class IconBadge(QLabel):
    def __init__(self, size: int = 52, parent=None):
        super().__init__(parent)
        self.setObjectName("BrandBadge")
        self.setFixedSize(size, size)
        self.setScaledContents(True)
        pixmap = QPixmap(str(asset_path("quantum-icon.png")))
        if not pixmap.isNull():
            self.setPixmap(pixmap)
        else:
            self.setText("QP")
            self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class CleanCheckBox(QCheckBox):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hovered = False

    def sizeHint(self):
        width = self.fontMetrics().horizontalAdvance(self.text()) + 40
        height = max(28, self.fontMetrics().height() + 10)
        return QSize(width, height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        enabled = self.isEnabled()
        active = enabled and (self._hovered or self.isDown())
        box_size = 18
        box = QRectF(2.0, (rect.height() - box_size) / 2 + 1.0, box_size, box_size)
        if self.isChecked():
            painter.setPen(QPen(QColor(15, 23, 42, 245 if active else 235), 1.9 if active else 1.8))
            painter.setBrush(QColor(15, 23, 42, 238 if active else (224 if enabled else 110)))
        else:
            painter.setPen(QPen(QColor(65, 82, 108, 245 if active else (230 if enabled else 110)), 1.9 if active else 1.8))
            painter.setBrush(QColor(255, 255, 255, 176 if active else (142 if enabled else 54)))
        painter.drawRoundedRect(box, 4, 4)
        if self.isChecked():
            pen = QPen(QColor(255, 255, 255, 240 if enabled else 150), 2.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            x = box.x()
            y = box.y()
            painter.drawLine(int(x + 4), int(y + 9), int(x + 8), int(y + 13))
            painter.drawLine(int(x + 8), int(y + 13), int(x + 14), int(y + 5))
        painter.setPen(QColor(63, 73, 89, 235 if enabled else 125))
        painter.drawText(rect.adjusted(34, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, self.text())
        painter.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)


class TerminalInput(QLineEdit):
    submitted = Signal(str)
    history_requested = Signal(int)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.submitted.emit(self.text())
            return
        if key == Qt.Key.Key_Up:
            self.history_requested.emit(-1)
            return
        if key == Qt.Key.Key_Down:
            self.history_requested.emit(1)
            return
        super().keyPressEvent(event)


class GlassCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LoginCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        inner = rect.adjusted(9, 9, -10, -10)
        gradient = QLinearGradient(inner.topLeft(), inner.bottomRight())
        gradient.setColorAt(0.0, QColor(250, 252, 255, 164))
        gradient.setColorAt(0.54, QColor(244, 247, 252, 132))
        gradient.setColorAt(1.0, QColor(232, 237, 246, 106))
        layers = [
            (rect.adjusted(0, 0, -1, -1), QColor(246, 249, 255, 8)),
            (rect.adjusted(4, 4, -5, -5), QColor(246, 249, 255, 34)),
        ]
        for layer_rect, color in layers:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(layer_rect, 10, 10)
        painter.setBrush(gradient)
        painter.drawRoundedRect(inner, 9, 9)
        painter.setPen(QPen(QColor(255, 255, 255, 72), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(inner, 9, 9)
        painter.end()


class AnimatedLoginBackground:
    def __init__(
        self,
        owner: QWidget,
        *,
        star_count: int = 90,
        interval_ms: int = 16,
        phase_step: float = 0.006,
        darken: int = 105,
    ):
        self.owner = owner
        self.background = QPixmap(str(asset_path("login-starry-bg.png")))
        self._scaled_background = QPixmap()
        self._scaled_size: tuple[int, int] | None = None
        self.phase_step = phase_step
        self.darken = darken
        rng = random.Random(20260607)
        self.stars = [
            (
                rng.random(),
                rng.random(),
                rng.uniform(0.6, 1.8),
                rng.uniform(0.35, 1.0),
                rng.uniform(0, math.tau),
            )
            for _ in range(star_count)
        ]
        self.phase = 0.0
        self.timer = QTimer(owner)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def tick(self):
        self.phase += self.phase_step
        self.owner.update()

    def _background_for(self, rect):
        if self.background.isNull():
            return QPixmap(), 0.0, 0.0
        scale = max(rect.width() / self.background.width(), rect.height() / self.background.height()) * 1.16
        width = max(1, int(self.background.width() * scale))
        height = max(1, int(self.background.height() * scale))
        key = (width, height)
        if self._scaled_size != key or self._scaled_background.isNull():
            self._scaled_background = self.background.scaled(
                width,
                height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._scaled_size = key
        return self._scaled_background, (rect.width() - width) / 2, (rect.height() - height) / 2

    def paint(self, painter: QPainter):
        rect = self.owner.rect()
        if rect.isEmpty():
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scaled, base_x, base_y = self._background_for(rect)
        if not scaled.isNull():
            offset_x = base_x + math.sin(self.phase * 0.55) * 24
            offset_y = base_y + math.cos(self.phase * 0.42) * 14
            painter.drawPixmap(QPointF(offset_x, offset_y), scaled)
        else:
            painter.fillRect(rect, QColor("#050811"))

        vignette = QLinearGradient(0, 0, 0, rect.height())
        vignette.setColorAt(0, QColor(5, 8, 16, 12))
        vignette.setColorAt(0.52, QColor(5, 8, 16, 42))
        vignette.setColorAt(1, QColor(5, 8, 16, self.darken))
        painter.fillRect(rect, vignette)

        for x, y, radius, base_alpha, phase in self.stars:
            drift = self.phase * 10 * (0.25 + radius * 0.16)
            px = (x * rect.width() + math.sin(self.phase + phase) * 8) % rect.width()
            py = (y * rect.height() + drift) % rect.height()
            pulse = 0.65 + 0.35 * math.sin(self.phase * 4 + phase)
            alpha = int(185 * base_alpha * pulse)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(206, 226, 255, max(35, min(alpha, 210))))
            painter.drawEllipse(QRectF(px, py, radius, radius))
        painter.restore()


class CosmicSurface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CosmicSurface")
        self.setAutoFillBackground(False)
        self.background = AnimatedLoginBackground(
            self,
            star_count=42,
            interval_ms=20,
            phase_step=0.0045,
            darken=150,
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        self.background.paint(painter)
        haze = QLinearGradient(0, 0, self.width(), self.height())
        haze.setColorAt(0.0, QColor(14, 22, 42, 115))
        haze.setColorAt(0.45, QColor(7, 12, 24, 58))
        haze.setColorAt(1.0, QColor(28, 35, 55, 120))
        painter.fillRect(self.rect(), haze)
        painter.end()


class Gauge(QWidget):
    def __init__(self, title: str, accent: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.accent = accent
        self.value = 0.0
        self.text = "-"
        self.detail = ""
        self.setMinimumSize(200, 188)

    def set_data(self, value: float, text: str, detail: str = ""):
        self.value = max(0.0, min(100.0, float(value or 0)))
        self.text = text
        self.detail = detail
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        cx = rect.width() // 2
        top = 10
        size = 94
        arc_rect = rect.adjusted(cx - size // 2, top, -(cx - size // 2), -(rect.height() - top - size))
        pen_bg = QPen(QColor(223, 230, 240, 210), 11)
        pen_bg.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_bg)
        painter.drawArc(arc_rect, 90 * 16, -360 * 16)
        color = self.accent
        if self.value > 85:
            color = "#ff453a"
        elif self.value > 60:
            color = "#ff9f0a"
        pen = QPen(QColor(color), 11)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(arc_rect, 90 * 16, int(-360 * 16 * self.value / 100.0))
        painter.setPen(QColor("#1d1d1f"))
        font = painter.font()
        font.setPointSize(15)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(arc_rect, Qt.AlignmentFlag.AlignCenter, self.text)
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#475467"))
        painter.drawText(0, top + size + 22, rect.width(), 20, Qt.AlignmentFlag.AlignCenter, self.title)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#7a8492"))
        painter.drawText(0, top + size + 46, rect.width(), 24, Qt.AlignmentFlag.AlignCenter, self.detail)


class NumberStat(QWidget):
    def __init__(self, title: str, accent: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.accent = accent
        self.text = "-"
        self.detail = ""
        self.setMinimumSize(200, 188)

    def set_data(self, value: float, text: str, detail: str = ""):
        self.text = text
        self.detail = detail
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(18, 18, -18, -18)
        accent = QColor(self.accent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 32))
        painter.drawRoundedRect(rect, 8, 8)
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(rect.left(), rect.top(), 5, rect.height()), 3, 3)

        font = painter.font()
        painter.setPen(QColor("#101828"))
        font.setPointSize(30)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect.adjusted(18, 14, -18, -70), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text)

        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#344054"))
        painter.drawText(rect.adjusted(18, 86, -18, -38), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title)

        font.setPointSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#667085"))
        painter.drawText(rect.adjusted(18, 116, -18, -16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.detail)
        painter.end()


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setObjectName("LoginDialog")
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setFixedSize(900, 720)
        self.setAutoFillBackground(False)
        self.background = AnimatedLoginBackground(
            self,
            star_count=82,
            interval_ms=16,
            phase_step=0.007,
            darken=72,
        )
        self.thread_pool = QThreadPool.globalInstance()
        self.result_data: LoginResult | None = None
        self.login_elapsed = 0
        self.login_timer = QTimer(self)
        self.login_timer.setInterval(1000)
        self.login_timer.timeout.connect(self.update_login_progress)
        self.connection_mode = MODE_BASTION
        self._loading_profile = False
        self.current_profile_id = ""
        profile_payload = load_cluster_profiles()
        self.profiles: list[dict] = list(profile_payload.get("profiles", []))
        self.last_profile_id = str(profile_payload.get("last_profile_id") or "")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addStretch(1)

        card = GlassCard()
        card.setFixedWidth(610)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(70)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 34))
        card.setGraphicsEffect(shadow)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(card)
        row.addStretch(1)
        root.addLayout(row)
        root.addStretch(1)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(14)
        badge = IconBadge(44)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel(APP_NAME)
        title.setObjectName("Title")
        subtitle = QLabel("输入 SSH 账号密码连接内网计算节点")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addWidget(badge)
        header.addLayout(title_box, 1)
        layout.addLayout(header)
        layout.addSpacing(4)

        self.profile_combo = QComboBox()
        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText("例如 A集群 / B集群")
        self.new_profile_btn = QPushButton("新建")
        self.new_profile_btn.setObjectName("ProfileAction")
        self.save_profile_btn = QPushButton("保存集群")
        self.save_profile_btn.setObjectName("ProfileAction")
        self.delete_profile_btn = QPushButton("删除")
        self.delete_profile_btn.setObjectName("ProfileDanger")
        for button, width in [
            (self.new_profile_btn, 72),
            (self.save_profile_btn, 96),
            (self.delete_profile_btn, 72),
        ]:
            button.setFixedSize(width, 36)

        profile_grid = QGridLayout()
        profile_grid.setHorizontalSpacing(10)
        profile_grid.setVerticalSpacing(8)
        profile_grid.setColumnMinimumWidth(0, 44)
        profile_grid.setColumnStretch(1, 1)
        saved_label = QLabel("集群")
        saved_label.setObjectName("FieldLabel")
        name_label = QLabel("名称")
        name_label.setObjectName("FieldLabel")
        profile_grid.addWidget(saved_label, 0, 0)
        profile_grid.addWidget(self.profile_combo, 0, 1)
        profile_actions = QHBoxLayout()
        profile_actions.setSpacing(8)
        profile_actions.addWidget(self.new_profile_btn)
        profile_actions.addWidget(self.save_profile_btn)
        profile_actions.addWidget(self.delete_profile_btn)
        profile_grid.addLayout(profile_actions, 0, 2)
        profile_grid.addWidget(name_label, 1, 0)
        profile_grid.addWidget(self.profile_name, 1, 1, 1, 2)
        layout.addLayout(profile_grid)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.bastion_mode_btn = QPushButton("跳板机方式")
        self.direct_mode_btn = QPushButton("直接连接")
        for button in [self.bastion_mode_btn, self.direct_mode_btn]:
            button.setObjectName("ModeToggle")
            button.setCheckable(True)
            mode_row.addWidget(button)
        layout.addLayout(mode_row)

        self.username = QLineEdit()
        self.username.setPlaceholderText("Linux / SSH 账号")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Linux / SSH 密码")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.bastion_host = QLineEdit(DEFAULT_BASTION_HOST)
        self.bastion_port = QLineEdit(str(DEFAULT_BASTION_PORT))
        self.inner_host = QLineEdit(DEFAULT_INNER_HOST)
        self.inner_port = QLineEdit(str(DEFAULT_INNER_PORT))
        self.use_key = CleanCheckBox("同时尝试本机 SSH 密钥")
        self.remember_password = CleanCheckBox("记住账号和密码")

        for widget in [
            self.username,
            self.password,
            self.bastion_host,
            self.bastion_port,
            self.inner_host,
            self.inner_port,
        ]:
            widget.setMinimumHeight(42)
        self.profile_name.setMinimumHeight(42)
        self.profile_combo.setMinimumHeight(42)
        for field in [self.bastion_host, self.bastion_port, self.inner_host, self.inner_port]:
            field.setObjectName("CompactInput")
            field.setFixedHeight(34)
        self.bastion_host.setMinimumWidth(0)
        self.inner_host.setMinimumWidth(0)
        self.bastion_port.setFixedWidth(84)
        self.inner_port.setFixedWidth(84)

        for label, widget in [("账号", self.username), ("密码", self.password)]:
            field_label = QLabel(label)
            field_label.setObjectName("FieldLabel")
            layout.addWidget(field_label)
            layout.addWidget(widget)

        options_row = QHBoxLayout()
        options_row.setSpacing(10)
        self.status = QLabel("")
        self.status.setObjectName("InlineStatus")
        self.status.setMinimumHeight(28)
        self.status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status.setWordWrap(False)
        options_row.addWidget(self.remember_password)
        options_row.addWidget(self.status, 1)
        layout.addLayout(options_row)

        settings_row = QHBoxLayout()
        self.settings_toggle = QPushButton("连接设置")
        self.settings_toggle.setObjectName("Ghost")
        self.settings_toggle.clicked.connect(self.toggle_settings)
        self.settings_summary = QLabel("请填写连接地址")
        self.settings_summary.setObjectName("Subtitle")
        settings_row.addWidget(self.settings_toggle)
        settings_row.addWidget(self.settings_summary, 1)
        layout.addLayout(settings_row)

        settings = QFrame()
        settings.setObjectName("SettingsPanel")
        settings.setMinimumHeight(146)
        self.settings_panel = settings
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(18, 16, 18, 16)
        settings_layout.setSpacing(10)
        settings_header = QHBoxLayout()
        settings_title = QLabel("连接设置")
        settings_title.setObjectName("SectionTitle")
        self.settings_note = QLabel("一般不用修改")
        self.settings_note.setObjectName("Subtitle")
        settings_header.addWidget(settings_title)
        settings_header.addStretch(1)
        settings_header.addWidget(self.use_key)
        settings_header.addWidget(self.settings_note)
        settings_layout.addLayout(settings_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(12)
        grid.setColumnMinimumWidth(0, 68)
        grid.setColumnMinimumWidth(2, 38)
        grid.setColumnMinimumWidth(3, 84)
        grid.setColumnStretch(1, 1)
        self.bastion_label = QLabel("跳板机")
        self.inner_label = QLabel("内网节点")
        self.bastion_port_label = QLabel("端口")
        self.inner_port_label = QLabel("端口")
        for label in [self.bastion_label, self.inner_label, self.bastion_port_label, self.inner_port_label]:
            label.setObjectName("FieldLabel")
            label.setFixedHeight(34)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.bastion_port_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.inner_port_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(self.bastion_label, 0, 0)
        grid.addWidget(self.bastion_host, 0, 1)
        grid.addWidget(self.bastion_port_label, 0, 2)
        grid.addWidget(self.bastion_port, 0, 3)
        grid.addWidget(self.inner_label, 1, 0)
        grid.addWidget(self.inner_host, 1, 1)
        grid.addWidget(self.inner_port_label, 1, 2)
        grid.addWidget(self.inner_port, 1, 3)
        self.bastion_row_widgets = [self.bastion_label, self.bastion_host, self.bastion_port_label, self.bastion_port]
        settings_layout.addLayout(grid)
        layout.addWidget(settings)
        self.settings_panel.setVisible(False)

        self.login_btn = QPushButton("登录")
        self.login_btn.setObjectName("Primary")
        self.login_btn.setFixedHeight(46)
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self.login)
        self.password.returnPressed.connect(self.login)
        layout.addStretch(1)
        layout.addWidget(self.login_btn)
        for field in [self.bastion_host, self.bastion_port, self.inner_host, self.inner_port]:
            field.textChanged.connect(self.update_settings_summary)
        self.profile_combo.currentIndexChanged.connect(self.on_profile_changed)
        self.new_profile_btn.clicked.connect(self.reset_new_profile)
        self.save_profile_btn.clicked.connect(self.save_current_profile)
        self.delete_profile_btn.clicked.connect(self.delete_current_profile)
        self.bastion_mode_btn.clicked.connect(lambda: self.set_connection_mode(MODE_BASTION))
        self.direct_mode_btn.clicked.connect(lambda: self.set_connection_mode(MODE_DIRECT))
        self.populate_profile_combo()
        if self.last_profile_id:
            self.apply_profile(self.last_profile_id)
        else:
            self.reset_new_profile(clear_status=True)
        if self.password.text():
            self.login_btn.setFocus()
        elif self.username.text():
            self.password.setFocus()
        else:
            self.username.setFocus()
        for button in self.findChildren(QPushButton):
            polish_button(button)

    def update_settings_summary(self):
        inner_host = self.inner_host.text().strip()
        inner_port = self.inner_port.text().strip()
        bastion_host = self.bastion_host.text().strip()
        bastion_port = self.bastion_port.text().strip()
        if self.connection_mode == MODE_DIRECT:
            if inner_host:
                self.settings_summary.setText(f"直连 {inner_host}:{inner_port or '22'}")
            else:
                self.settings_summary.setText("直接连接 · 请填写主机地址")
        else:
            if bastion_host or inner_host:
                left = f"{bastion_host or '跳板机'}:{bastion_port or '22'}"
                right = f"{inner_host or '内网节点'}:{inner_port or '22'}"
                self.settings_summary.setText(f"{left} -> {right}")
            else:
                self.settings_summary.setText("跳板机方式 · 请填写跳板机和内网节点")

    def populate_profile_combo(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("新建集群配置", "")
        for profile in self.profiles:
            name = str(profile.get("name") or "未命名集群")
            self.profile_combo.addItem(name, str(profile.get("id") or ""))
        self.profile_combo.blockSignals(False)
        self.set_profile_combo(self.current_profile_id)

    def set_profile_combo(self, profile_id: str):
        self.profile_combo.blockSignals(True)
        for index in range(self.profile_combo.count()):
            if str(self.profile_combo.itemData(index) or "") == profile_id:
                self.profile_combo.setCurrentIndex(index)
                break
        else:
            self.profile_combo.setCurrentIndex(0)
        self.profile_combo.blockSignals(False)

    def find_profile(self, profile_id: str) -> dict | None:
        for profile in self.profiles:
            if str(profile.get("id") or "") == profile_id:
                return profile
        return None

    def on_profile_changed(self):
        if self._loading_profile:
            return
        profile_id = str(self.profile_combo.currentData() or "")
        if profile_id:
            self.apply_profile(profile_id)
        else:
            self.reset_new_profile()

    def apply_profile(self, profile_id: str):
        profile = self.find_profile(profile_id)
        if profile is None:
            self.reset_new_profile(clear_status=True)
            return
        self._loading_profile = True
        self.current_profile_id = profile_id
        self.set_profile_combo(profile_id)
        self.profile_name.setText(str(profile.get("name") or ""))
        self.username.setText(str(profile.get("username") or ""))
        self.password.setText(str(profile.get("password") or ""))
        self.bastion_host.setText(str(profile.get("bastion_host") or DEFAULT_BASTION_HOST))
        self.bastion_port.setText(str(profile.get("bastion_port") or DEFAULT_BASTION_PORT))
        self.inner_host.setText(str(profile.get("inner_host") or DEFAULT_INNER_HOST))
        self.inner_port.setText(str(profile.get("inner_port") or DEFAULT_INNER_PORT))
        self.use_key.setChecked(bool(profile.get("use_key", False)))
        self.remember_password.setChecked(bool(profile.get("password")))
        self.set_connection_mode(str(profile.get("mode") or MODE_BASTION), clear_status=True)
        self.status.setText("")
        self._loading_profile = False

    def reset_new_profile(self, checked: bool = False, clear_status: bool = False):
        self._loading_profile = True
        self.current_profile_id = ""
        self.set_profile_combo("")
        self.profile_name.clear()
        self.username.clear()
        self.password.clear()
        self.bastion_host.setText(DEFAULT_BASTION_HOST)
        self.bastion_port.setText(str(DEFAULT_BASTION_PORT))
        self.inner_host.setText(DEFAULT_INNER_HOST)
        self.inner_port.setText(str(DEFAULT_INNER_PORT))
        self.use_key.setChecked(False)
        self.remember_password.setChecked(False)
        self.set_connection_mode(MODE_BASTION, clear_status=True)
        if clear_status:
            self.status.setText("")
        else:
            self.status.setText("已切换到新的集群配置")
        self._loading_profile = False

    def set_connection_mode(self, mode: str, clear_status: bool = False):
        self.connection_mode = _normalize_connection_mode(mode)
        is_direct = self.connection_mode == MODE_DIRECT
        self.bastion_mode_btn.setChecked(not is_direct)
        self.direct_mode_btn.setChecked(is_direct)
        for widget in self.bastion_row_widgets:
            widget.setVisible(not is_direct)
        self.inner_label.setText("直连主机" if is_direct else "内网节点")
        self.settings_note.setText("直接连接目标 SSH" if is_direct else "一般不用修改")
        self.settings_panel.setMinimumHeight(112 if is_direct else 146)
        self.update_settings_summary()
        if clear_status:
            return
        self.status.setText("已切换为直连模式" if is_direct else "已切换为跳板机模式")

    def auto_profile_name(self, credentials: ClusterCredentials | None = None) -> str:
        if credentials is None:
            if self.connection_mode == MODE_DIRECT:
                return self.inner_host.text().strip() or "直连集群"
            return self.bastion_host.text().strip() or "跳板机集群"
        if credentials.direct:
            return credentials.inner_host or "直连集群"
        return credentials.bastion_host or "跳板机集群"

    def profile_from_fields(self, require_name: bool = False) -> dict:
        name = self.profile_name.text().strip()
        if require_name and not name:
            raise ValueError("请先给这个集群配置起一个名称")
        if not name:
            name = self.auto_profile_name()
        inner_port = self.parse_port(self.inner_port, "直连主机" if self.connection_mode == MODE_DIRECT else "内网节点")
        inner_host = self.inner_host.text().strip()
        if not inner_host:
            raise ValueError("请填写直连主机地址" if self.connection_mode == MODE_DIRECT else "请填写内网节点地址")
        bastion_port = DEFAULT_BASTION_PORT
        bastion_host = self.bastion_host.text().strip()
        if self.connection_mode == MODE_BASTION:
            bastion_port = self.parse_port(self.bastion_port, "跳板机")
            if not bastion_host:
                raise ValueError("请填写跳板机地址")
        return {
            "id": self.current_profile_id or uuid4().hex,
            "name": name,
            "mode": self.connection_mode,
            "username": self.username.text().strip(),
            "password": self.password.text() if self.remember_password.isChecked() else "",
            "bastion_host": bastion_host,
            "bastion_port": bastion_port,
            "inner_host": inner_host,
            "inner_port": inner_port,
            "use_key": self.use_key.isChecked(),
        }

    def profile_from_credentials(self, credentials: ClusterCredentials) -> dict:
        name = self.profile_name.text().strip() or self.auto_profile_name(credentials)
        return {
            "id": self.current_profile_id or uuid4().hex,
            "name": name,
            "mode": MODE_DIRECT if credentials.direct else MODE_BASTION,
            "username": credentials.username,
            "password": credentials.password if self.remember_password.isChecked() else "",
            "bastion_host": credentials.bastion_host,
            "bastion_port": credentials.bastion_port,
            "inner_host": credentials.inner_host,
            "inner_port": credentials.inner_port,
            "use_key": credentials.use_key,
        }

    def upsert_profile(self, profile: dict):
        profile_id = str(profile.get("id") or uuid4().hex)
        profile["id"] = profile_id
        for index, existing in enumerate(self.profiles):
            if str(existing.get("id") or "") == profile_id:
                self.profiles[index] = profile
                break
        else:
            self.profiles.append(profile)
        self.current_profile_id = profile_id
        self.profile_name.setText(str(profile.get("name") or ""))
        save_cluster_profiles(self.profiles, profile_id)
        remove_legacy_remembered_login()
        self.populate_profile_combo()

    def save_current_profile(self, checked: bool = False, silent: bool = False) -> bool:
        try:
            profile = self.profile_from_fields(require_name=True)
            self.upsert_profile(profile)
        except Exception as exc:
            if not silent:
                self.status.setText(str(exc))
            return False
        if not silent:
            self.status.setText(f"已保存集群：{profile['name']}")
        return True

    def save_login_profile(self, credentials: ClusterCredentials) -> bool:
        try:
            profile = self.profile_from_credentials(credentials)
            self.upsert_profile(profile)
        except Exception:
            return False
        return True

    def delete_current_profile(self):
        profile_id = self.current_profile_id or str(self.profile_combo.currentData() or "")
        profile = self.find_profile(profile_id)
        if profile is None:
            self.status.setText("当前是新集群配置，还没有保存")
            return
        reply = QMessageBox.question(
            self,
            "删除集群配置",
            f"确定删除“{profile.get('name', '未命名集群')}”吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.profiles = [item for item in self.profiles if str(item.get("id") or "") != profile_id]
        save_cluster_profiles(self.profiles, "")
        self.populate_profile_combo()
        self.reset_new_profile(clear_status=True)
        self.status.setText("已删除集群配置")

    def toggle_settings(self):
        visible = not self.settings_panel.isVisible()
        self.settings_panel.setVisible(visible)
        self.settings_toggle.setText("收起设置" if visible else "连接设置")

    def set_login_enabled(self, enabled: bool):
        for widget in [
            self.username,
            self.password,
            self.bastion_host,
            self.bastion_port,
            self.inner_host,
            self.inner_port,
            self.use_key,
            self.remember_password,
            self.profile_combo,
            self.profile_name,
            self.new_profile_btn,
            self.save_profile_btn,
            self.delete_profile_btn,
            self.bastion_mode_btn,
            self.direct_mode_btn,
            self.settings_toggle,
            self.login_btn,
        ]:
            widget.setEnabled(enabled)

    def update_login_progress(self):
        self.login_elapsed += 1
        self.status.setText(f"正在建立 SSH 会话，已等待 {self.login_elapsed} 秒")

    def parse_port(self, widget: QLineEdit, label: str) -> int:
        try:
            port = int(widget.text().strip())
        except ValueError as exc:
            raise ValueError(f"{label}端口必须是数字") from exc
        if not 1 <= port <= 65535:
            raise ValueError(f"{label}端口必须在 1-65535 之间")
        return port

    def paintEvent(self, event):
        painter = QPainter(self)
        self.background.paint(painter)
        painter.end()

    def login(self):
        username = self.username.text().strip()
        password = self.password.text()
        if not username:
            self.status.setText("请填写账号")
            self.username.setFocus()
            return
        if not password:
            self.status.setText("请填写密码")
            self.password.setFocus()
            return
        try:
            inner_port = self.parse_port(
                self.inner_port, "直连主机" if self.connection_mode == MODE_DIRECT else "内网节点"
            )
            bastion_port = DEFAULT_BASTION_PORT
            if self.connection_mode == MODE_BASTION:
                bastion_port = self.parse_port(self.bastion_port, "跳板机")
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        inner_host = self.inner_host.text().strip()
        bastion_host = self.bastion_host.text().strip()
        if not inner_host:
            self.status.setText("请填写直连主机地址" if self.connection_mode == MODE_DIRECT else "请填写内网节点地址")
            self.inner_host.setFocus()
            return
        if self.connection_mode == MODE_BASTION and not bastion_host:
            self.status.setText("请填写跳板机地址")
            self.bastion_host.setFocus()
            return

        self.set_login_enabled(False)
        self.login_btn.setText("连接中...")
        self.login_elapsed = 0
        self.status.setText("正在建立 SSH 会话，已等待 0 秒")
        self.login_timer.start()
        credentials = ClusterCredentials(
            username=username,
            password=password,
            bastion_host=bastion_host,
            bastion_port=bastion_port,
            inner_host=inner_host,
            inner_port=inner_port,
            direct=self.connection_mode == MODE_DIRECT,
            key_path=DEFAULT_KEY_PATH,
            use_key=self.use_key.isChecked(),
        )
        worker = Worker(self._login_worker, credentials)
        worker.signals.finished.connect(self._login_ok)
        worker.signals.error.connect(self._login_error)
        self.thread_pool.start(worker)

    def _login_worker(self, credentials: ClusterCredentials):
        health = get_login_health(credentials)
        return LoginResult(credentials, health)

    def _login_ok(self, result: LoginResult):
        self.login_timer.stop()
        should_save = self.remember_password.isChecked() or bool(self.profile_name.text().strip()) or bool(self.current_profile_id)
        if should_save and not self.save_login_profile(result.credentials):
            QMessageBox.warning(self, "保存失败", "登录成功，但保存集群配置失败。")
        elif not should_save:
            remove_legacy_remembered_login()
        self.result_data = result
        self.accept()

    def _login_error(self, message: str):
        self.login_timer.stop()
        self.set_login_enabled(True)
        self.login_btn.setText("登录")
        self.status.setText("登录失败")
        QMessageBox.warning(self, "登录失败", message)


class MainWindow(QMainWindow):
    def __init__(self, login: LoginResult):
        super().__init__()
        self.credentials = login.credentials
        self.health = login.health
        close_credentials_connection(self.credentials)
        self.thread_pool = QThreadPool.globalInstance()
        self.current_path = self.health.get("home") or f"/home/{self.credentials.username}"
        self.terminal_cwd = self.current_path
        self.terminal_history: list[str] = []
        self.terminal_history_index = 0
        self.show_hidden = False
        self.selected_job = ""
        self._op_seq = 0
        self._active_ops: dict[str, int] = {}
        self._op_text: dict[str, str] = {}
        self._workers: dict[int, Worker] = {}
        self._scope_credentials: dict[str, ClusterCredentials] = {}
        self._op_credentials: dict[int, ClusterCredentials] = {}
        self.last_refresh_text = "尚未刷新"
        self.auto_refresh = QTimer(self)
        self.auto_refresh.setInterval(10000)
        self.auto_refresh.timeout.connect(self.auto_refresh_current)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1320, 820)
        self._build()
        self._polish_static_controls()
        self.auto_refresh.start()
        self.status_line.setText("等待首次刷新...")
        QTimer.singleShot(450, self.refresh_dashboard)

    def _polish_static_controls(self):
        for button in self.findChildren(QPushButton):
            polish_button(button)
        self.tabs.tabBar().setCursor(Qt.CursorShape.PointingHandCursor)

    def _build(self):
        central = CosmicSurface()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 22, 28, 24)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("MainTitle")
        subtitle = QLabel(f"{self.credentials.username} · {self.health.get('hostname', '-')}")
        subtitle.setObjectName("MainSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_current)
        header.addWidget(self.refresh_btn)
        root.addLayout(header)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self._build_dashboard()
        self._build_jobs()
        self._build_files()
        self._build_terminal()
        footer = QHBoxLayout()
        self.status_line = QLabel("就绪")
        self.status_line.setObjectName("MainSubtitle")
        self.refresh_hint = QLabel("自动刷新: 总览/作业每 10 秒")
        self.refresh_hint.setObjectName("MainSubtitle")
        footer.addWidget(self.status_line)
        footer.addStretch(1)
        footer.addWidget(self.refresh_hint)
        root.addLayout(footer)
        self.tabs.currentChanged.connect(lambda _: self.refresh_current())

    def _build_dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        gauges = QHBoxLayout()
        gauges.setSpacing(16)
        self.g_cpu = Gauge("CPU", "#0a84ff")
        self.g_mem = Gauge("内存", "#00c7be")
        self.g_disk = Gauge("磁盘", "#ff9f0a")
        self.g_jobs = NumberStat("运行作业", "#bf5af2")
        for gauge in [self.g_cpu, self.g_mem, self.g_disk, self.g_jobs]:
            frame = panel()
            frame.setMinimumHeight(224)
            box = QVBoxLayout(frame)
            box.setContentsMargins(14, 10, 14, 14)
            box.addWidget(gauge)
            gauges.addWidget(frame)
        layout.addLayout(gauges)
        lower = QHBoxLayout()
        lower.setSpacing(16)
        jobs_panel = panel()
        jobs_layout = QVBoxLayout(jobs_panel)
        jobs_layout.setContentsMargins(14, 14, 14, 14)
        title = QLabel("近期作业")
        title.setObjectName("SectionTitle")
        jobs_layout.addWidget(title)
        self.recent_jobs = QTableWidget(0, 6)
        self._setup_table(self.recent_jobs, ["来源", "名称", "PID", "CPU核", "目录", "时间"])
        self._size_table_columns(self.recent_jobs, {0: 72, 2: 82, 3: 72, 5: 130})
        jobs_layout.addWidget(self.recent_jobs)
        lower.addWidget(jobs_panel, 2)

        info_panel = panel()
        info_panel.setMinimumWidth(320)
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(18, 16, 18, 16)
        info_layout.setSpacing(12)
        info_title = QLabel("节点摘要")
        info_title.setObjectName("SectionTitle")
        info_layout.addWidget(info_title)
        self.node_hostname = QLabel("-")
        self.node_hostname.setObjectName("FieldLabel")
        self.node_cpu = QLabel("-")
        self.node_cpu.setObjectName("Subtitle")
        self.node_scheduler = QLabel("-")
        self.node_scheduler.setObjectName("Subtitle")
        self.node_refresh = QLabel("-")
        self.node_refresh.setObjectName("Subtitle")
        for widget in [self.node_hostname, self.node_cpu, self.node_scheduler, self.node_refresh]:
            widget.setWordWrap(True)
            info_layout.addWidget(widget)
        info_layout.addStretch(1)
        lower.addWidget(info_panel, 1)
        layout.addLayout(lower, 1)
        self.tabs.addTab(page, "总览")

    def _build_jobs(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)
        form_panel = panel()
        form_panel.setMinimumHeight(184)
        form_panel.setMaximumHeight(224)
        form_wrap = QVBoxLayout(form_panel)
        form_wrap.setContentsMargins(16, 14, 16, 18)
        form_wrap.setSpacing(10)
        form_title = QLabel("提交作业")
        form_title.setObjectName("SectionTitle")
        form_wrap.addWidget(form_title)
        form = QHBoxLayout()
        form.setSpacing(18)
        self.job_name = QLineEdit()
        self.job_name.setPlaceholderText("例如 xxz_N12_run1")
        self.job_dir = QLineEdit(self.current_path)
        for field in [self.job_name, self.job_dir]:
            field.setObjectName("JobInput")
            field.setFixedHeight(36)
        self.job_cmd = QPlainTextEdit()
        self.job_cmd.setPlaceholderText("bash run.sh\n./main > out.txt")
        self.job_cmd.setMinimumHeight(106)
        self.submit_btn = QPushButton("提交作业")
        self.submit_btn.setObjectName("SubmitJob")
        self.submit_btn.setFixedHeight(44)
        self.submit_btn.clicked.connect(self.submit_job)

        left = QGridLayout()
        left.setHorizontalSpacing(10)
        left.setVerticalSpacing(10)
        left.setContentsMargins(0, 0, 0, 2)
        left.setColumnMinimumWidth(0, 44)
        left.setColumnStretch(1, 1)
        left.setRowMinimumHeight(2, 46)
        name_label = QLabel("名称")
        dir_label = QLabel("目录")
        for label in [name_label, dir_label]:
            label.setObjectName("FieldLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        left.addWidget(name_label, 0, 0)
        left.addWidget(self.job_name, 0, 1)
        left.addWidget(dir_label, 1, 0)
        left.addWidget(self.job_dir, 1, 1)
        left.addWidget(self.submit_btn, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        left_box = QWidget()
        left_box.setLayout(left)

        right = QVBoxLayout()
        right.setSpacing(8)
        cmd_label = QLabel("命令")
        cmd_label.setObjectName("FieldLabel")
        right.addWidget(cmd_label)
        right.addWidget(self.job_cmd, 1)
        right_box = QWidget()
        right_box.setLayout(right)

        form.addWidget(left_box, 1)
        form.addWidget(right_box, 1)
        form_wrap.addLayout(form)
        layout.addWidget(form_panel, 0)

        jobs_panel = panel()
        jobs_panel.setMinimumHeight(250)
        jobs_box = QVBoxLayout(jobs_panel)
        jobs_box.setContentsMargins(14, 14, 14, 14)
        jobs_title = QLabel("平台作业")
        jobs_title.setObjectName("SectionTitle")
        jobs_box.addWidget(jobs_title)
        self.jobs_table = QTableWidget(0, 8)
        self._setup_table(self.jobs_table, ["来源", "状态", "名称", "PID", "CPU核", "时间", "目录", "操作"])
        self._size_table_columns(self.jobs_table, {0: 72, 1: 88, 3: 82, 4: 72, 5: 130, 7: 230})
        jobs_box.addWidget(self.jobs_table, 1)
        layout.addWidget(jobs_panel, 1)

        log_panel = panel()
        log_panel.setMaximumHeight(170)
        log_box = QVBoxLayout(log_panel)
        log_box.setContentsMargins(14, 12, 14, 14)
        log_title = QLabel("日志预览")
        log_title.setObjectName("SectionTitle")
        log_box.addWidget(log_title)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(112)
        log_box.addWidget(self.log_view)
        layout.addWidget(log_panel, 0)
        self.tabs.addTab(page, "作业")

    def _build_files(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)
        toolbar_panel = panel()
        toolbar_panel.setMinimumHeight(72)
        toolbar_box = QVBoxLayout(toolbar_panel)
        toolbar_box.setContentsMargins(14, 12, 14, 12)
        toolbar_title = QLabel("远程文件")
        toolbar_title.setObjectName("SectionTitle")
        toolbar_box.addWidget(toolbar_title)
        toolbar = QHBoxLayout()
        self.path_edit = QLineEdit(self.current_path)
        open_btn = QPushButton("打开")
        open_btn.clicked.connect(lambda: self.load_files(self.path_edit.text()))
        up_btn = QPushButton("上级")
        up_btn.clicked.connect(self.go_parent)
        new_btn = QPushButton("新建目录")
        new_btn.clicked.connect(self.mkdir)
        upload_btn = QPushButton("上传")
        upload_btn.clicked.connect(self.upload)
        self.hidden_cb = CleanCheckBox("显示隐藏文件")
        self.hidden_cb.stateChanged.connect(self.toggle_hidden)
        toolbar.addWidget(self.path_edit, 1)
        for widget in [open_btn, up_btn, new_btn, upload_btn, self.hidden_cb]:
            toolbar.addWidget(widget)
        toolbar_box.addLayout(toolbar)
        layout.addWidget(toolbar_panel)
        body = QHBoxLayout()
        body.setSpacing(14)
        files_panel = panel()
        files_box = QVBoxLayout(files_panel)
        files_box.setContentsMargins(14, 14, 14, 14)
        files_title = QLabel("目录内容")
        files_title.setObjectName("SectionTitle")
        files_box.addWidget(files_title)
        self.files_table = QTableWidget(0, 4)
        self._setup_table(self.files_table, ["名称", "大小", "修改时间", "操作"])
        self._size_table_columns(self.files_table, {1: 96, 2: 150, 3: 260})
        self.file_rows: list[dict] = []
        self.files_table.cellDoubleClicked.connect(self.open_file_row)
        files_box.addWidget(self.files_table, 1)
        body.addWidget(files_panel, 2)
        preview_panel = panel()
        preview_box = QVBoxLayout(preview_panel)
        preview_box.setContentsMargins(14, 14, 14, 14)
        preview_title = QLabel("文本预览")
        preview_title.setObjectName("SectionTitle")
        preview_box.addWidget(preview_title)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("选择文本文件后预览")
        preview_box.addWidget(self.preview, 1)
        body.addWidget(preview_panel, 1)
        layout.addLayout(body, 1)
        self.tabs.addTab(page, "文件")

    def _build_terminal(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        top_panel = panel()
        top_panel.setMinimumHeight(76)
        top_layout = QHBoxLayout(top_panel)
        top_layout.setContentsMargins(16, 12, 16, 12)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel("命令行")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("真实通过当前 SSH 会话执行命令；长时间计算建议放到作业页或使用 nohup。")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        top_layout.addLayout(title_box, 1)
        self.terminal_pwd_btn = QPushButton("pwd")
        self.terminal_clear_btn = QPushButton("清屏")
        self.terminal_home_btn = QPushButton("回到 Home")
        for button in [self.terminal_pwd_btn, self.terminal_clear_btn, self.terminal_home_btn]:
            button.setObjectName("Ghost")
            top_layout.addWidget(button)
        self.terminal_pwd_btn.clicked.connect(lambda: self.submit_terminal_command("pwd"))
        self.terminal_clear_btn.clicked.connect(self.clear_terminal)
        self.terminal_home_btn.clicked.connect(lambda: self.submit_terminal_command("cd ~ && pwd"))
        layout.addWidget(top_panel, 0)

        terminal_panel = panel()
        terminal_layout = QVBoxLayout(terminal_panel)
        terminal_layout.setContentsMargins(14, 14, 14, 14)
        terminal_layout.setSpacing(10)
        self.terminal_output = QPlainTextEdit()
        self.terminal_output.setObjectName("TerminalOutput")
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setMinimumHeight(460)
        self.terminal_output.setFont(QFont("Consolas", 10))
        terminal_layout.addWidget(self.terminal_output, 1)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self.terminal_prompt = QLabel("")
        self.terminal_prompt.setObjectName("TerminalPrompt")
        self.terminal_prompt.setMinimumWidth(220)
        self.terminal_input = TerminalInput()
        self.terminal_input.setObjectName("TerminalInput")
        self.terminal_input.setPlaceholderText("输入 Linux 命令，例如 ls -lh、cd xxz、tail -n 50 out.txt")
        self.terminal_input.submitted.connect(self.submit_terminal_command)
        self.terminal_input.history_requested.connect(self.navigate_terminal_history)
        self.terminal_run_btn = QPushButton("执行")
        self.terminal_run_btn.setObjectName("Primary")
        self.terminal_run_btn.setFixedHeight(42)
        self.terminal_run_btn.clicked.connect(lambda: self.submit_terminal_command(self.terminal_input.text()))
        input_row.addWidget(self.terminal_prompt)
        input_row.addWidget(self.terminal_input, 1)
        input_row.addWidget(self.terminal_run_btn)
        terminal_layout.addLayout(input_row)

        layout.addWidget(terminal_panel, 1)
        self.update_terminal_prompt()
        self.append_terminal_text(
            f"Connected to {self.credentials.username}@{self.health.get('hostname', '-')}\n"
            "This panel runs normal shell commands. Use the Jobs tab for long calculations.\n"
        )
        self.tabs.addTab(page, "命令行")

    def _setup_table(self, table: QTableWidget, headers: list[str]):
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.verticalHeader().setDefaultSectionSize(44)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setStretchLastSection(False)

    def _size_table_columns(self, table: QTableWidget, fixed: dict[int, int]):
        header = table.horizontalHeader()
        for col, width in fixed.items():
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(col, width)

    def update_terminal_prompt(self):
        host = self.health.get("hostname", "-")
        home = self.health.get("home") or ""
        display_cwd = self.terminal_cwd
        if home and self.terminal_cwd.startswith(home):
            display_cwd = self.terminal_cwd.replace(home, "~", 1)
        prompt = f"{self.credentials.username}@{host}:{display_cwd}$"
        self.terminal_prompt.setText(prompt)
        self.terminal_prompt.setToolTip(prompt)

    def append_terminal_text(self, text: str):
        self.terminal_output.appendPlainText(text.rstrip("\n"))
        bar = self.terminal_output.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_terminal_enabled(self, enabled: bool):
        self.terminal_input.setEnabled(enabled)
        self.terminal_run_btn.setEnabled(enabled)
        self.terminal_pwd_btn.setEnabled(enabled)
        self.terminal_home_btn.setEnabled(enabled)
        if enabled:
            self.terminal_input.setFocus()

    def clear_terminal(self):
        self.terminal_output.clear()
        self.append_terminal_text(f"Connected to {self.credentials.username}@{self.health.get('hostname', '-')}")

    def navigate_terminal_history(self, direction: int):
        if not self.terminal_history:
            return
        self.terminal_history_index = max(0, min(len(self.terminal_history), self.terminal_history_index + direction))
        if self.terminal_history_index == len(self.terminal_history):
            self.terminal_input.clear()
        else:
            self.terminal_input.setText(self.terminal_history[self.terminal_history_index])
            self.terminal_input.setCursorPosition(len(self.terminal_input.text()))

    def submit_terminal_command(self, command: str):
        command = command.strip()
        if not command:
            return False
        if command == "clear":
            self.clear_terminal()
            self.terminal_input.clear()
            return True
        if "terminal" in self._active_ops:
            self.status_line.setText("命令仍在执行中")
            return False
        self.append_terminal_text(f"{self.terminal_prompt.text()} {command}")
        if not self.terminal_history or self.terminal_history[-1] != command:
            self.terminal_history.append(command)
        self.terminal_history_index = len(self.terminal_history)
        self.terminal_input.clear()
        self.set_terminal_enabled(False)
        started = self._run_remote(
            "terminal",
            lambda credentials: run_shell_command(credentials, command, self.terminal_cwd, timeout=120),
            self.apply_terminal_result,
            "命令执行中...",
            timeout_ms=130000,
            show_error=False,
        )
        if not started:
            self.set_terminal_enabled(True)
        return started

    def apply_terminal_result(self, data: dict):
        stdout = str(data.get("stdout") or "")
        stderr = str(data.get("stderr") or "")
        if stdout:
            self.append_terminal_text(stdout)
        if stderr:
            self.append_terminal_text("[stderr]\n" + stderr)
        exit_status = int(data.get("exit_status") or 0)
        if exit_status != 0:
            self.append_terminal_text(f"[exit {exit_status}]")
        self.terminal_cwd = str(data.get("cwd") or self.terminal_cwd)
        self.update_terminal_prompt()
        self.set_terminal_enabled(True)

    def terminal_failed(self, message: str):
        if hasattr(self, "terminal_output"):
            self.append_terminal_text("[error] " + message)
            self.set_terminal_enabled(True)

    def _current_scope(self) -> str:
        idx = self.tabs.currentIndex()
        if idx == 0:
            return "dashboard"
        if idx == 1:
            return "jobs"
        if idx == 2:
            return "files"
        return "terminal"

    def _credentials_for_scope(self, scope: str) -> ClusterCredentials:
        credentials = self._scope_credentials.get(scope)
        if credentials is None:
            credentials = clone_credentials(self.credentials)
            self._scope_credentials[scope] = credentials
        return credentials

    def _discard_scope_credentials(self, scope: str):
        credentials = self._scope_credentials.pop(scope, None)
        if credentials is not None:
            close_credentials_connection(credentials)

    def _close_all_connections(self):
        seen: set[int] = set()
        for credentials in [self.credentials, *self._scope_credentials.values(), *self._op_credentials.values()]:
            ident = id(credentials)
            if ident in seen:
                continue
            seen.add(ident)
            close_credentials_connection(credentials)
        self._scope_credentials.clear()
        self._op_credentials.clear()

    def closeEvent(self, event):
        self.auto_refresh.stop()
        self._close_all_connections()
        super().closeEvent(event)

    def _update_refresh_button(self):
        scope = self._current_scope()
        if scope in self._active_ops:
            self.refresh_btn.setText(self._op_text.get(scope, "处理中..."))
        else:
            self.refresh_btn.setText("刷新")
        self.refresh_btn.setEnabled(True)

    def _run(
        self,
        scope: str,
        fn,
        done,
        busy_text="处理中...",
        timeout_ms: int = 30000,
        show_error: bool = False,
        op_credentials: ClusterCredentials | None = None,
    ):
        if scope in self._active_ops:
            self.status_line.setText(f"{busy_text}仍在进行中")
            self._update_refresh_button()
            return False
        self._op_seq += 1
        op_id = self._op_seq
        self._active_ops[scope] = op_id
        self._op_text[scope] = busy_text
        if op_credentials is not None:
            self._op_credentials[op_id] = op_credentials
        self.status_line.setText(busy_text)
        self._update_refresh_button()
        worker = Worker(fn)
        self._workers[op_id] = worker
        worker.signals.finished.connect(lambda data, op=op_id, sc=scope: self._done(sc, op, done, data))
        worker.signals.error.connect(
            lambda message, op=op_id, sc=scope: self._error(sc, op, message, show_error)
        )
        self.thread_pool.start(worker)
        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, lambda op=op_id, sc=scope: self._operation_timeout(sc, op))
        return True

    def _run_remote(
        self,
        scope: str,
        fn,
        done,
        busy_text="处理中...",
        timeout_ms: int = 30000,
        show_error: bool = False,
    ):
        credentials = self._credentials_for_scope(scope)

        def work():
            return fn(credentials)

        return self._run(scope, work, done, busy_text, timeout_ms, show_error, op_credentials=credentials)

    def _operation_timeout(self, scope: str, op_id: int):
        if self._active_ops.get(scope) != op_id:
            return
        self._active_ops.pop(scope, None)
        self._op_text.pop(scope, None)
        credentials = self._op_credentials.get(op_id)
        if credentials is not None:
            close_credentials_connection(credentials)
        self._discard_scope_credentials(scope)
        self._update_refresh_button()
        self.status_line.setText(f"{self._scope_label(scope)}超时，可继续操作")
        if scope == "terminal":
            self.terminal_failed("命令超时；长时间计算建议使用作业页或 nohup。")

    def _done(self, scope: str, op_id: int, done, data):
        self._workers.pop(op_id, None)
        credentials = self._op_credentials.pop(op_id, None)
        if self._active_ops.get(scope) != op_id:
            if credentials is not None and self._scope_credentials.get(scope) is not credentials:
                close_credentials_connection(credentials)
            return
        self._active_ops.pop(scope, None)
        self._op_text.pop(scope, None)
        self._update_refresh_button()
        self.last_refresh_text = datetime.now().strftime("%H:%M:%S")
        self.status_line.setText(f"就绪 · {self.last_refresh_text}")
        done(data)

    def _error(self, scope: str, op_id: int, message: str, show_error: bool):
        self._workers.pop(op_id, None)
        credentials = self._op_credentials.pop(op_id, None)
        if self._active_ops.get(scope) != op_id:
            if credentials is not None and self._scope_credentials.get(scope) is not credentials:
                close_credentials_connection(credentials)
            return
        self._active_ops.pop(scope, None)
        self._op_text.pop(scope, None)
        if credentials is not None:
            close_credentials_connection(credentials)
        self._discard_scope_credentials(scope)
        self._update_refresh_button()
        self.status_line.setText(f"{self._scope_label(scope)}失败: {message}")
        if scope == "terminal":
            self.terminal_failed(message)
        if show_error:
            QMessageBox.warning(self, "操作失败", message)

    def _scope_label(self, scope: str) -> str:
        return {
            "dashboard": "总览刷新",
            "jobs": "作业刷新",
            "files": "文件读取",
            "log": "日志读取",
            "job-action": "作业操作",
            "file-action": "文件操作",
            "terminal": "命令执行",
        }.get(scope, "操作")

    def auto_refresh_current(self):
        idx = self.tabs.currentIndex()
        if idx == 0 and "dashboard" not in self._active_ops:
            self.refresh_dashboard()
        elif idx == 1 and "jobs" not in self._active_ops:
            self.refresh_jobs()

    def refresh_current(self):
        idx = self.tabs.currentIndex()
        if idx == 0:
            self.refresh_dashboard()
        elif idx == 1:
            self.refresh_jobs()
        elif idx == 2:
            self.load_files(self.current_path)
        else:
            self.status_line.setText("命令行已就绪")
            self._update_refresh_button()
            if hasattr(self, "terminal_input"):
                self.terminal_input.setFocus()

    def refresh_dashboard(self):
        return self._run_remote(
            "dashboard",
            lambda credentials: get_dashboard(credentials, 80),
            self._apply_dashboard,
            "刷新中...",
            timeout_ms=25000,
        )

    def _combined_jobs(self, data: dict) -> list[dict]:
        platform_jobs = []
        for job in data.get("jobs", []):
            if is_internal_test_job(job):
                continue
            row = dict(job)
            row.setdefault("source", "platform")
            platform_jobs.append(row)
        external_jobs = []
        for task in data.get("processes", []):
            if task.get("error"):
                continue
            row = dict(task)
            row["source"] = "external"
            row.setdefault("status", "running")
            row.setdefault("id", f"external-{row.get('pid', '')}")
            external_jobs.append(row)
        return platform_jobs + external_jobs

    def _apply_dashboard(self, data: dict):
        metrics = data.get("metrics", {})
        jobs = self._combined_jobs(data)
        platform_jobs = [job for job in jobs if job.get("source") != "external"]
        external_jobs = [job for job in jobs if job.get("source") == "external"]
        disk = (metrics.get("disks") or [{}])[0]
        mem = metrics.get("memory") or {}
        platform_running = len([j for j in platform_jobs if j.get("status") in ("running", "submitted")])
        external_running = len(external_jobs)
        running = platform_running + external_running
        self.g_cpu.set_data(metrics.get("cpu", {}).get("overall", 0), f"{metrics.get('cpu', {}).get('overall', 0):.1f}%", "总使用率")
        self.g_mem.set_data(mem.get("percent", 0), f"{mem.get('percent', 0):.1f}%", f"{human_bytes(mem.get('used'))} / {human_bytes(mem.get('total'))}")
        self.g_disk.set_data(disk.get("percent", 0), f"{disk.get('percent', 0):.0f}%", disk.get("mount", "/"))
        self.g_jobs.set_data(18 if running == 0 else 68, str(running), f"平台 {platform_running} · 外部 {external_running}")
        scheduler = self.health.get("scheduler") or {}
        enabled = [name for name, ok in scheduler.items() if ok]
        self.node_hostname.setText(f"节点: {self.health.get('hostname', '-')}")
        self.node_cpu.setText(f"CPU: {self.health.get('cpu_count', '-')} 核 · Uptime {format_duration(metrics.get('uptime_seconds'))}")
        self.node_scheduler.setText("调度器: " + (", ".join(enabled) if enabled else "未检测到 Slurm/PBS"))
        self.node_refresh.setText(f"最近刷新: {datetime.now().strftime('%H:%M:%S')}")
        self._fill_jobs_table(self.recent_jobs, jobs[:8], actions=False)

    def refresh_jobs(self):
        return self._run_remote(
            "jobs",
            lambda credentials: get_dashboard(credentials, 80),
            self._apply_jobs,
            "刷新中...",
            timeout_ms=25000,
        )

    def _apply_jobs(self, data: dict):
        jobs = self._combined_jobs(data)
        self._fill_jobs_table(self.jobs_table, jobs, actions=True)

    def _fill_jobs_table(self, table: QTableWidget, jobs: list[dict], actions: bool):
        table.clearSpans()
        if not jobs:
            table.setRowCount(1)
            item = QTableWidgetItem("暂无作业")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QBrush(QColor("#69707d")))
            table.setItem(0, 0, item)
            table.setSpan(0, 0, 1, table.columnCount())
            return
        table.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            status = str(job.get("status", ""))
            source = str(job.get("source") or "platform")
            source_text, source_fg, source_bg = source_palette(source)
            display_name = job_display_name(job)
            command_tip = str(job.get("args") or job.get("command") or display_name)
            if actions:
                vals = [
                    source_text,
                    status,
                    display_name,
                    job.get("pid", ""),
                    job_cpu_text(job),
                    job_time_text(job),
                    job.get("workdir", ""),
                ]
            else:
                vals = [
                    source_text,
                    display_name,
                    job.get("pid", ""),
                    job_cpu_text(job),
                    job.get("workdir", ""),
                    job_time_text(job),
                ]
            for col, value in enumerate(vals):
                item = QTableWidgetItem(str(value))
                item.setToolTip(command_tip if col in (1, 2) else "")
                if col == 0:
                    item.setForeground(QBrush(QColor(source_fg)))
                    item.setBackground(QBrush(QColor(source_bg)))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if actions and col == 1:
                    fg, bg = status_palette(str(status))
                    item.setForeground(QBrush(QColor(fg)))
                    item.setBackground(QBrush(QColor(bg)))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, col, item)
            if actions:
                actions_widget = QWidget()
                box = QHBoxLayout(actions_widget)
                box.setContentsMargins(7, 5, 7, 5)
                box.setSpacing(7)
                stop_btn = QPushButton("停止")
                stop_btn.setObjectName("TableDanger")
                stop_btn.setFixedHeight(28)
                polish_button(stop_btn)
                if source == "external":
                    pid = int(job.get("pid") or 0)
                    stop_btn.clicked.connect(lambda _, p=pid: self.stop_external_task(p))
                    stop_btn.setEnabled(pid > 1)
                    box.addStretch(1)
                else:
                    log_btn = QPushButton("输出")
                    err_btn = QPushButton("错误")
                    for btn in [log_btn, err_btn]:
                        btn.setObjectName("TableAction")
                        btn.setFixedHeight(28)
                        polish_button(btn)
                    job_id = job.get("id", "")
                    log_btn.clicked.connect(lambda _, jid=job_id: self.load_log(jid, "stdout"))
                    err_btn.clicked.connect(lambda _, jid=job_id: self.load_log(jid, "stderr"))
                    stop_btn.clicked.connect(lambda _, jid=job_id: self.stop_job(jid))
                    stop_btn.setEnabled(str(status).lower() in ("running", "submitted"))
                    box.addWidget(log_btn)
                    box.addWidget(err_btn)
                box.addWidget(stop_btn)
                table.setCellWidget(row, 7, actions_widget)

    def submit_job(self):
        command = self.job_cmd.toPlainText().strip()
        if not command:
            QMessageBox.information(self, "需要命令", "请填写要运行的命令。")
            return
        return self._run_remote(
            "job-action",
            lambda credentials: submit_job(credentials, self.job_name.text(), command, self.job_dir.text()),
            lambda _: self.refresh_jobs(),
            "提交中...",
            timeout_ms=30000,
            show_error=True,
        )

    def stop_job(self, job_id: str):
        if not job_id:
            return
        if QMessageBox.question(self, "停止作业", f"确定停止作业 {job_id}？") == QMessageBox.StandardButton.Yes:
            return self._run_remote(
                "job-action",
                lambda credentials: stop_job(credentials, job_id),
                lambda _: self.refresh_jobs(),
                "停止中...",
                timeout_ms=30000,
                show_error=True,
            )

    def stop_external_task(self, pid: int):
        if pid <= 1:
            return
        if QMessageBox.question(self, "停止外部任务", f"确定停止外部任务 PID {pid}？") == QMessageBox.StandardButton.Yes:
            return self._run_remote(
                "job-action",
                lambda credentials: kill_process(credentials, pid, False),
                lambda _: self.refresh_jobs(),
                "停止外部任务...",
                timeout_ms=30000,
                show_error=True,
            )

    def load_log(self, job_id: str, stream: str = "stdout"):
        label = "stdout" if stream == "stdout" else "stderr"
        return self._run_remote(
            "log",
            lambda credentials: get_job_logs(credentials, job_id, stream),
            lambda data: self.log_view.setPlainText(f"[{label}] {job_id}\n\n{data.get('text', '')}"),
            "读取日志...",
            timeout_ms=25000,
            show_error=True,
        )

    def load_files(self, path: str):
        self.current_path = path
        self.path_edit.setText(path)
        return self._run_remote(
            "files",
            lambda credentials: list_files(credentials, path),
            self._apply_files,
            "读取中...",
            timeout_ms=25000,
        )

    def _apply_files(self, data: dict):
        self.current_path = data.get("path", self.current_path)
        self.path_edit.setText(self.current_path)
        items = data.get("items", [])
        if not self.show_hidden:
            items = [item for item in items if not item["name"].startswith(".")]
        self.file_rows = items
        if not items:
            self.files_table.setRowCount(1)
            item = QTableWidgetItem("当前目录没有可显示文件")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QBrush(QColor("#69707d")))
            self.files_table.setItem(0, 0, item)
            self.files_table.setSpan(0, 0, 1, self.files_table.columnCount())
            return
        self.files_table.clearSpans()
        self.files_table.setRowCount(len(items))
        for row, item in enumerate(items):
            vals = [
                ("▸ " if item["is_dir"] else "") + item["name"],
                "目录" if item["is_dir"] else human_bytes(item["size"]),
                format_ts(item.get("mtime")),
            ]
            for col, value in enumerate(vals):
                self.files_table.setItem(row, col, QTableWidgetItem(str(value)))
            actions_widget = QWidget()
            box = QHBoxLayout(actions_widget)
            box.setContentsMargins(7, 5, 7, 5)
            box.setSpacing(7)
            open_btn = QPushButton("打开" if item["is_dir"] else "预览")
            rename_btn = QPushButton("改名")
            delete_btn = QPushButton("删除")
            for btn in [open_btn, rename_btn]:
                btn.setObjectName("TableAction")
                btn.setFixedHeight(28)
                polish_button(btn)
            delete_btn.setObjectName("TableDanger")
            delete_btn.setFixedHeight(28)
            polish_button(delete_btn)
            remote_path = item["path"]
            if item["is_dir"]:
                open_btn.clicked.connect(lambda _, p=remote_path: self.load_files(p))
            else:
                open_btn.clicked.connect(lambda _, p=remote_path: self.preview_file(p))
                dl_btn = QPushButton("下载")
                dl_btn.setObjectName("TableAction")
                dl_btn.setFixedHeight(28)
                polish_button(dl_btn)
                dl_btn.clicked.connect(lambda _, p=remote_path: self.download(p))
                box.addWidget(dl_btn)
            rename_btn.clicked.connect(lambda _, p=remote_path: self.rename(p))
            delete_btn.clicked.connect(lambda _, p=remote_path: self.delete(p))
            box.insertWidget(0, open_btn)
            box.addWidget(rename_btn)
            box.addWidget(delete_btn)
            self.files_table.setCellWidget(row, 3, actions_widget)

    def open_file_row(self, row: int, column: int):
        if row < 0 or row >= len(self.file_rows):
            return
        item = self.file_rows[row]
        if item.get("is_dir"):
            self.load_files(item["path"])
        else:
            self.preview_file(item["path"])

    def go_parent(self):
        path = self.current_path.rstrip("/") or "/"
        self.load_files(posixpath.dirname(path) or "/")

    def toggle_hidden(self):
        self.show_hidden = self.hidden_cb.isChecked()
        self.load_files(self.current_path)

    def preview_file(self, path: str):
        return self._run_remote(
            "file-action",
            lambda credentials: read_text_file(credentials, path),
            lambda data: self.preview.setPlainText(data.get("text", "")),
            "预览中...",
            timeout_ms=25000,
            show_error=True,
        )

    def download(self, path: str):
        target, _ = QFileDialog.getSaveFileName(self, "保存文件", Path(path).name)
        if not target:
            return

        def work():
            credentials = clone_credentials(self.credentials)
            try:
                _name, chunks = download_file_stream(credentials, path)
                with open(target, "wb") as fh:
                    for chunk in chunks:
                        fh.write(chunk)
                return target
            finally:
                close_credentials_connection(credentials)

        return self._run(
            "file-action",
            work,
            lambda _: QMessageBox.information(self, "下载完成", target),
            "下载中...",
            timeout_ms=120000,
            show_error=True,
        )

    def upload(self):
        local, _ = QFileDialog.getOpenFileName(self, "选择上传文件")
        if not local:
            return
        def work():
            credentials = clone_credentials(self.credentials)
            try:
                with open(local, "rb") as fh:
                    return upload_file(credentials, self.current_path, Path(local).name, fh)
            finally:
                close_credentials_connection(credentials)

        return self._run(
            "file-action",
            work,
            lambda _: self.load_files(self.current_path),
            "上传中...",
            timeout_ms=120000,
            show_error=True,
        )

    def mkdir(self):
        name, ok = QInputDialog.getText(self, "新建目录", "目录名")
        if ok and name.strip():
            return self._run_remote(
                "file-action",
                lambda credentials: mkdir_path(credentials, self.current_path, name.strip()),
                lambda _: self.load_files(self.current_path),
                "创建中...",
                timeout_ms=30000,
                show_error=True,
            )

    def rename(self, path: str):
        name, ok = QInputDialog.getText(self, "改名", "新名称", text=Path(path).name)
        if ok and name.strip():
            return self._run_remote(
                "file-action",
                lambda credentials: rename_path(credentials, path, name.strip()),
                lambda _: self.load_files(self.current_path),
                "改名中...",
                timeout_ms=30000,
                show_error=True,
            )

    def delete(self, path: str):
        message = f"确定删除这个远程路径？\n\n{path}\n\n只会删除文件或空目录，无法撤销。"
        if QMessageBox.question(self, "确认删除", message) == QMessageBox.StandardButton.Yes:
            return self._run_remote(
                "file-action",
                lambda credentials: delete_path(credentials, path),
                lambda _: self.load_files(self.current_path),
                "删除中...",
                timeout_ms=30000,
                show_error=True,
            )


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(app_icon())
    app.setStyleSheet(STYLE)
    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted or login.result_data is None:
        return 0
    window = MainWindow(login.result_data)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
