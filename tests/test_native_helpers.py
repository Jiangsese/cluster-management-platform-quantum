import time
import re

from PySide6.QtWidgets import QApplication

import native_app
from backend.app import remote
from backend.app import ssh_client
from backend.app.sessions import ClusterCredentials
from backend.app.ssh_client import CommandResult
from native_app import (
    LoginResult,
    clone_credentials,
    human_bytes,
    is_internal_test_job,
    protect_secret,
    status_palette,
    unprotect_secret,
)


def qapp():
    return QApplication.instance() or QApplication([])


def pump_until(app, predicate, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_human_bytes_formats_large_values():
    assert human_bytes(0) == "0 B"
    assert human_bytes(1536) == "1.5 KB"
    assert human_bytes(1024**3) == "1.0 GB"


def test_internal_test_jobs_are_hidden():
    assert is_internal_test_job({"name": "quantum_console_smoke"})
    assert is_internal_test_job({"command": "echo kill-test-start; sleep 120"})
    assert not is_internal_test_job({"name": "xxz_N12_run1", "command": "bash run.sh"})


def test_status_palette_has_failure_color():
    fg, bg = status_palette("failed")
    assert fg.startswith("#")
    assert bg.startswith("#")
    assert fg != bg


def test_protect_secret_round_trips():
    encoded = protect_secret("fake-password-for-test")
    assert encoded != "fake-password-for-test"
    assert unprotect_secret(encoded) == "fake-password-for-test"


def test_clone_credentials_does_not_share_connection():
    credentials = ClusterCredentials(
        username="alice",
        password="secret",
        bastion_host="bastion",
        bastion_port=22,
        inner_host="inner",
        inner_port=22,
        direct=True,
    )
    credentials.connection = object()
    cloned = clone_credentials(credentials)
    assert cloned.username == credentials.username
    assert cloned.password == credentials.password
    assert cloned.direct is True
    assert cloned.connection is None


def test_cluster_profiles_store_passwords_per_cluster(monkeypatch, tmp_path):
    monkeypatch.setattr(native_app, "DATA_DIR", tmp_path)
    monkeypatch.setattr(native_app, "PROFILES_FILE", tmp_path / "cluster_profiles.json")
    monkeypatch.setattr(native_app, "REMEMBER_FILE", tmp_path / "remembered_login.json")
    profiles = [
        {
            "id": "lab",
            "name": "A集群",
            "mode": native_app.MODE_BASTION,
            "username": "user-a",
            "password": "pass-a",
            "bastion_host": "bastion-a",
            "bastion_port": 23456,
            "inner_host": "inner-a",
            "inner_port": 22,
            "use_key": False,
        },
        {
            "id": "direct",
            "name": "直连集群",
            "mode": native_app.MODE_DIRECT,
            "username": "user-b",
            "password": "pass-b",
            "bastion_host": "",
            "bastion_port": 22,
            "inner_host": "direct-host",
            "inner_port": 10022,
            "use_key": True,
        },
    ]

    native_app.save_cluster_profiles(profiles, "direct")
    raw = (tmp_path / "cluster_profiles.json").read_text(encoding="utf-8")
    assert "pass-a" not in raw
    assert "pass-b" not in raw

    loaded = native_app.load_cluster_profiles()
    assert loaded["last_profile_id"] == "direct"
    assert [profile["name"] for profile in loaded["profiles"]] == ["A集群", "直连集群"]
    assert loaded["profiles"][0]["password"] == "pass-a"
    assert loaded["profiles"][1]["password"] == "pass-b"
    assert loaded["profiles"][1]["mode"] == native_app.MODE_DIRECT


def test_direct_connection_skips_bastion(monkeypatch):
    calls = []

    class FakeTransport:
        def __init__(self):
            self.keepalive = None

        def is_active(self):
            return True

        def set_keepalive(self, seconds):
            self.keepalive = seconds

    class FakeClient:
        def __init__(self):
            self.transport = FakeTransport()
            self.closed = False

        def get_transport(self):
            return self.transport

        def close(self):
            self.closed = True

    def fake_connect_host(host, port, username, password, key_path, sock=None):
        calls.append((host, port, username, password, key_path, sock))
        return FakeClient()

    monkeypatch.setattr(ssh_client, "_connect_host", fake_connect_host)
    credentials = ClusterCredentials(
        username="jh",
        password="secret",
        bastion_host="unused-bastion",
        bastion_port=22,
        inner_host="direct-host",
        inner_port=10022,
        direct=True,
        use_key=False,
    )
    connection = ssh_client.PersistentInnerConnection(credentials)

    inner = connection._ensure_locked()

    assert inner is connection._inner
    assert connection._bastion is None
    assert calls == [("direct-host", 10022, "jh", "secret", None, None)]


def test_login_health_parses_read_only_probe(monkeypatch):
    def fake_exec_inner(credentials, command, timeout=30):
        return CommandResult(
            stdout="\n".join(
                [
                    "hostname=node-a",
                    "username=alice",
                    "home=/home/alice",
                    "cwd=/home/alice",
                    "os=CentOS Linux release 7.8.2003 (Core)",
                    "cpu_count=112",
                    "scheduler_squeue=0",
                    "scheduler_sacct=0",
                    "scheduler_qstat=0",
                ]
            ),
            stderr="",
            exit_status=0,
        )

    monkeypatch.setattr(remote, "exec_inner", fake_exec_inner)
    credentials = ClusterCredentials(
        username="alice",
        password="secret",
        bastion_host="bastion",
        bastion_port=22,
        inner_host="inner",
        inner_port=22,
    )
    health = remote.get_login_health(credentials)
    assert health["hostname"] == "node-a"
    assert health["cpu_count"] == 112
    assert health["scheduler"] == {"squeue": False, "sacct": False, "qstat": False}


def test_run_shell_command_parses_status_and_cwd(monkeypatch):
    def fake_exec_inner(credentials, command, timeout=120):
        marker = re.search(r"__CLUSTER_PANEL_DONE_[0-9a-f]+__", command).group(0)
        return CommandResult(
            stdout=f"hello from shell\n{marker}7:/home/jh/xxz\n",
            stderr="warning text\n",
            exit_status=7,
        )

    monkeypatch.setattr(remote, "exec_inner", fake_exec_inner)
    credentials = ClusterCredentials(
        username="jh",
        password="secret",
        bastion_host="bastion",
        bastion_port=22,
        inner_host="inner",
        inner_port=22,
    )

    result = remote.run_shell_command(credentials, "echo hello", "/home/jh")

    assert result["stdout"] == "hello from shell"
    assert result["stderr"] == "warning text\n"
    assert result["exit_status"] == 7
    assert result["cwd"] == "/home/jh/xxz"


def test_file_scope_runs_while_dashboard_scope_is_stuck(monkeypatch):
    app = qapp()
    monkeypatch.setattr(native_app.MainWindow, "refresh_dashboard", lambda self: None)

    def fake_list_files(credentials, path):
        return {
            "path": path,
            "items": [
                {
                    "name": "xxz",
                    "path": f"{path.rstrip('/')}/xxz",
                    "is_dir": True,
                    "size": 4096,
                    "mtime": 1_780_830_000,
                }
            ],
        }

    monkeypatch.setattr(native_app, "list_files", fake_list_files)
    login = LoginResult(
        ClusterCredentials(
            username="alice",
            password="secret",
            bastion_host="bastion",
            bastion_port=22,
            inner_host="inner",
            inner_port=22,
        ),
        {"home": "/home/alice", "hostname": "node-a", "cpu_count": 112, "scheduler": {}},
    )
    window = native_app.MainWindow(login)
    window.auto_refresh.stop()
    window.tabs.blockSignals(True)
    window.tabs.setCurrentIndex(2)
    window.tabs.blockSignals(False)
    window._active_ops["dashboard"] = 999
    window._op_text["dashboard"] = "刷新中..."

    assert window.load_files("/home/alice") is True
    assert pump_until(app, lambda: "files" not in window._active_ops)
    assert "dashboard" in window._active_ops
    assert window.files_table.rowCount() == 1
    assert "xxz" in window.files_table.item(0, 0).text()
    window.close()


def test_terminal_tab_has_independent_scope(monkeypatch):
    app = qapp()
    monkeypatch.setattr(native_app.MainWindow, "refresh_dashboard", lambda self: None)
    load_files_calls = []
    monkeypatch.setattr(native_app.MainWindow, "load_files", lambda self, path: load_files_calls.append(path))
    login = LoginResult(
        ClusterCredentials(
            username="alice",
            password="secret",
            bastion_host="bastion",
            bastion_port=22,
            inner_host="inner",
            inner_port=22,
        ),
        {"home": "/home/alice", "hostname": "node-a", "cpu_count": 112, "scheduler": {}},
    )
    window = native_app.MainWindow(login)
    window.auto_refresh.stop()

    window.tabs.setCurrentIndex(3)
    app.processEvents()

    assert window.tabs.tabText(3) == "命令行"
    assert window._current_scope() == "terminal"
    assert load_files_calls == []
    window.close()


def test_external_tasks_are_merged_into_jobs_table(monkeypatch):
    app = qapp()
    monkeypatch.setattr(native_app.MainWindow, "refresh_dashboard", lambda self: None)
    login = LoginResult(
        ClusterCredentials(
            username="alice",
            password="secret",
            bastion_host="bastion",
            bastion_port=22,
            inner_host="inner",
            inner_port=22,
        ),
        {"home": "/home/alice", "hostname": "node-a", "cpu_count": 112, "scheduler": {}},
    )
    window = native_app.MainWindow(login)
    window.auto_refresh.stop()
    data = {
        "metrics": {
            "cpu": {"overall": 12.3},
            "memory": {"percent": 20, "used": 1, "total": 2},
            "disks": [{"percent": 30, "mount": "/"}],
            "uptime_seconds": 3600,
        },
        "jobs": [
            {
                "id": "job1",
                "name": "run1",
                "pid": "111",
                "status": "running",
                "workdir": "/home/alice/run",
                "created_at": "2026-01-01T01:02",
            }
        ],
        "processes": [
            {
                "id": "external-222",
                "source": "external",
                "pid": 222,
                "status": "running",
                "cpu_cores": 2.5,
                "elapsed": "01:20:03",
                "command": "python",
                "args": "python run.py",
                "workdir": "/home/alice/x",
            }
        ],
    }

    window._apply_jobs(data)
    assert window.jobs_table.columnCount() == 8
    assert window.jobs_table.rowCount() == 2
    assert window.jobs_table.item(0, 0).text() == "平台"
    assert window.jobs_table.item(1, 0).text() == "外部"
    assert window.jobs_table.item(1, 4).text() == "2.50"
    assert window.jobs_table.cellWidget(1, 7) is not None
    window._apply_dashboard(data)
    assert "外部 1" in window.g_jobs.detail
    window.close()


def test_operation_timeout_releases_only_that_scope(monkeypatch):
    app = qapp()
    monkeypatch.setattr(native_app.MainWindow, "refresh_dashboard", lambda self: None)
    login = LoginResult(
        ClusterCredentials(
            username="alice",
            password="secret",
            bastion_host="bastion",
            bastion_port=22,
            inner_host="inner",
            inner_port=22,
        ),
        {"home": "/home/alice", "hostname": "node-a", "cpu_count": 112, "scheduler": {}},
    )
    window = native_app.MainWindow(login)
    window.auto_refresh.stop()
    window.tabs.blockSignals(True)
    window.tabs.setCurrentIndex(2)
    window.tabs.blockSignals(False)
    window._active_ops["dashboard"] = 10
    window._active_ops["files"] = 11
    window._op_text["files"] = "读取中..."

    window._operation_timeout("dashboard", 10)
    app.processEvents()
    assert "dashboard" not in window._active_ops
    assert "files" in window._active_ops
    assert window.refresh_btn.text() == "读取中..."

    window._operation_timeout("files", 11)
    app.processEvents()
    assert "files" not in window._active_ops
    assert window.refresh_btn.text() == "刷新"
    window.close()
