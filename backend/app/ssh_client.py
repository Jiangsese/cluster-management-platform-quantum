from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
import time
from typing import Iterator

import paramiko

from .sessions import ClusterCredentials


class ClusterSSHError(RuntimeError):
    pass


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_status: int


def _load_key(path: Path | None) -> str | None:
    if path and path.exists():
        return str(path)
    return None


def _connect_host(
    host: str,
    port: int,
    username: str,
    password: str,
    key_path: Path | None,
    sock=None,
) -> paramiko.SSHClient:
    errors: list[str] = []
    attempts = []
    key_filename = _load_key(key_path)
    if key_filename:
        attempts.append({"key_filename": key_filename, "password": password})
    attempts.append({"password": password})

    for auth in attempts:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                host,
                port=port,
                username=username,
                timeout=20,
                banner_timeout=20,
                auth_timeout=20,
                look_for_keys=False,
                allow_agent=False,
                sock=sock,
                **auth,
            )
            return client
        except Exception as exc:  # paramiko raises several auth/socket subclasses.
            client.close()
            errors.append(f"{type(exc).__name__}: {exc}")
            if sock is not None:
                break
    raise ClusterSSHError("; ".join(errors) or "SSH connection failed")


class PersistentInnerConnection:
    def __init__(self, credentials: ClusterCredentials) -> None:
        self.credentials = credentials
        self._lock = RLock()
        self._bastion: paramiko.SSHClient | None = None
        self._inner: paramiko.SSHClient | None = None

    def close(self) -> None:
        with self._lock:
            self._close_locked()

    def _close_locked(self) -> None:
        if self._inner is not None:
            self._inner.close()
            self._inner = None
        if self._bastion is not None:
            self._bastion.close()
            self._bastion = None

    @staticmethod
    def _active(client: paramiko.SSHClient | None) -> bool:
        if client is None:
            return False
        transport = client.get_transport()
        return bool(transport and transport.is_active())

    def _ensure_locked(self) -> paramiko.SSHClient:
        if self._active(self._inner):
            return self._inner  # type: ignore[return-value]
        self._close_locked()
        credentials = self.credentials
        key_path = credentials.key_path if credentials.use_key else None
        if credentials.direct:
            self._inner = _connect_host(
                credentials.inner_host,
                credentials.inner_port,
                credentials.username,
                credentials.password,
                key_path,
            )
            inner_transport = self._inner.get_transport()
            if inner_transport is not None:
                inner_transport.set_keepalive(30)
            return self._inner

        self._bastion = _connect_host(
            credentials.bastion_host,
            credentials.bastion_port,
            credentials.username,
            credentials.password,
            key_path,
        )
        transport = self._bastion.get_transport()
        if transport is None:
            raise ClusterSSHError("Bastion transport is not available")
        transport.set_keepalive(30)
        channel = transport.open_channel(
            "direct-tcpip",
            (credentials.inner_host, credentials.inner_port),
            ("127.0.0.1", 0),
        )
        self._inner = _connect_host(
            credentials.inner_host,
            credentials.inner_port,
            credentials.username,
            credentials.password,
            key_path,
            sock=channel,
        )
        inner_transport = self._inner.get_transport()
        if inner_transport is not None:
            inner_transport.set_keepalive(30)
        return self._inner

    def exec(self, command: str, timeout: int = 30) -> CommandResult:
        with self._lock:
            try:
                ssh = self._ensure_locked()
                stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
                stdin.close()
                channel = stdout.channel
                channel.settimeout(1.0)
                deadline = time.monotonic() + timeout
                out_chunks: list[bytes] = []
                err_chunks: list[bytes] = []
                while True:
                    while channel.recv_ready():
                        out_chunks.append(channel.recv(32768))
                    while channel.recv_stderr_ready():
                        err_chunks.append(channel.recv_stderr(32768))
                    if channel.exit_status_ready():
                        while channel.recv_ready():
                            out_chunks.append(channel.recv(32768))
                        while channel.recv_stderr_ready():
                            err_chunks.append(channel.recv_stderr(32768))
                        status = channel.recv_exit_status()
                        break
                    if time.monotonic() > deadline:
                        channel.close()
                        self._close_locked()
                        raise ClusterSSHError(f"Remote command timed out after {timeout} seconds")
                    time.sleep(0.03)
                out = b"".join(out_chunks).decode("utf-8", errors="replace")
                err = b"".join(err_chunks).decode("utf-8", errors="replace")
                return CommandResult(stdout=out, stderr=err, exit_status=status)
            except ClusterSSHError:
                raise
            except Exception as exc:
                self._close_locked()
                raise ClusterSSHError(f"{type(exc).__name__}: {exc}") from exc

    @contextmanager
    def sftp(self):
        with self._lock:
            sftp = None
            try:
                ssh = self._ensure_locked()
                sftp = ssh.open_sftp()
                yield sftp
            except ClusterSSHError:
                raise
            except Exception as exc:
                raise ClusterSSHError(f"{type(exc).__name__}: {exc}") from exc
            finally:
                if sftp is not None:
                    sftp.close()


def _connection(credentials: ClusterCredentials) -> PersistentInnerConnection:
    connection = getattr(credentials, "connection", None)
    if connection is None:
        connection = PersistentInnerConnection(credentials)
        credentials.connection = connection
    return connection


@contextmanager
def inner_client(credentials: ClusterCredentials) -> Iterator[paramiko.SSHClient]:
    connection = _connection(credentials)
    with connection._lock:
        yield connection._ensure_locked()


def exec_inner(credentials: ClusterCredentials, command: str, timeout: int = 30) -> CommandResult:
    return _connection(credentials).exec(command, timeout)


@contextmanager
def sftp_inner(credentials: ClusterCredentials):
    with _connection(credentials).sftp() as sftp:
        yield sftp
