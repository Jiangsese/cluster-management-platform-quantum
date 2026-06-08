from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import (
    APP_NAME,
    DEFAULT_BASTION_HOST,
    DEFAULT_BASTION_PORT,
    DEFAULT_INNER_HOST,
    DEFAULT_INNER_PORT,
    DEFAULT_KEY_PATH,
    FRONTEND_DIR,
)
from .database import init_db
from .remote import (
    delete_path,
    download_file_stream,
    get_dashboard,
    get_health,
    get_job_logs,
    get_metrics,
    get_processes,
    kill_process,
    list_files,
    list_jobs,
    mkdir_path,
    read_text_file,
    rename_path,
    run_shell_command,
    submit_job,
    stop_job,
    upload_file,
)
from .sessions import ClusterCredentials, session_store
from .ssh_client import ClusterSSHError


app = FastAPI(title=APP_NAME)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    bastion_host: str = DEFAULT_BASTION_HOST
    bastion_port: int = DEFAULT_BASTION_PORT
    inner_host: str = DEFAULT_INNER_HOST
    inner_port: int = DEFAULT_INNER_PORT
    direct: bool = False
    use_key: bool = False


class JobSubmitRequest(BaseModel):
    name: str = ""
    command: str = Field(min_length=1)
    workdir: str = Field(default="~")


class RenameRequest(BaseModel):
    path: str
    new_name: str


class MkdirRequest(BaseModel):
    parent: str
    name: str


class ShellCommandRequest(BaseModel):
    command: str = Field(min_length=1)
    cwd: str = "~"
    timeout: int = Field(default=120, ge=1, le=600)


def api_error(exc: Exception, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def get_credentials(x_cluster_session: str | None = Header(default=None)) -> ClusterCredentials:
    credentials = session_store.get(x_cluster_session)
    if credentials is None:
        raise HTTPException(status_code=401, detail="请先登录集群")
    return credentials


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.post("/api/auth/login")
def login(payload: LoginRequest):
    credentials = ClusterCredentials(
        username=payload.username.strip(),
        password=payload.password,
        bastion_host=payload.bastion_host.strip(),
        bastion_port=payload.bastion_port,
        inner_host=payload.inner_host.strip(),
        inner_port=payload.inner_port,
        direct=payload.direct,
        key_path=DEFAULT_KEY_PATH,
        use_key=payload.use_key,
    )
    try:
        health = get_health(credentials)
    except ClusterSSHError as exc:
        raise api_error(Exception("SSH 登录失败，请检查账号、密码、网络或跳板机设置。详细信息：" + str(exc)), 401)
    except Exception as exc:
        raise api_error(exc, 401)
    token = session_store.create(credentials)
    return {"token": token, "user": credentials.username, "health": health}


@app.post("/api/auth/logout")
def logout(x_cluster_session: str | None = Header(default=None)):
    session_store.delete(x_cluster_session)
    return {"ok": True}


@app.get("/api/cluster/health")
def cluster_health(credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return get_health(credentials)
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/metrics")
def metrics(credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return get_metrics(credentials)
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/dashboard")
def dashboard(limit: int = 80, credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return get_dashboard(credentials, limit=max(10, min(limit, 200)))
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/processes")
def processes(limit: int = 80, credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return get_processes(credentials, limit=max(10, min(limit, 200)))
    except Exception as exc:
        raise api_error(exc)


@app.post("/api/processes/{pid}/kill")
def process_kill(pid: int, force: bool = False, credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return kill_process(credentials, pid, force)
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/jobs")
def jobs(credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return list_jobs(credentials)
    except Exception as exc:
        raise api_error(exc)


@app.post("/api/jobs")
def create_job(payload: JobSubmitRequest, credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return submit_job(credentials, payload.name, payload.command, payload.workdir)
    except Exception as exc:
        raise api_error(exc)


@app.post("/api/jobs/{job_id}/stop")
def kill_job(job_id: str, credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return stop_job(credentials, job_id)
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/logs/{job_id}")
def logs(job_id: str, stream: str = "stdout", limit: int = 60000, credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return get_job_logs(credentials, job_id, stream, max(1000, min(limit, 500000)))
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/files")
def files(path: str | None = None, credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return list_files(credentials, path)
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/files/read")
def file_read(path: str, limit: int = 200000, credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return read_text_file(credentials, path, limit)
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/files/download")
def file_download(path: str, credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        filename, iterator = download_file_stream(credentials, path)
    except Exception as exc:
        raise api_error(exc)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return StreamingResponse(
        iterator,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/files/upload")
def file_upload(path: str, file: UploadFile = File(...), credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return upload_file(credentials, path, file.filename or "upload.bin", file.file)
    except Exception as exc:
        raise api_error(exc)


@app.delete("/api/files")
def file_delete(path: str, credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return delete_path(credentials, path)
    except Exception as exc:
        raise api_error(exc)


@app.post("/api/files/rename")
def file_rename(payload: RenameRequest, credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return rename_path(credentials, payload.path, payload.new_name)
    except Exception as exc:
        raise api_error(exc)


@app.post("/api/files/mkdir")
def file_mkdir(payload: MkdirRequest, credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return mkdir_path(credentials, payload.parent, payload.name)
    except Exception as exc:
        raise api_error(exc)


@app.post("/api/terminal/exec")
def terminal_exec(payload: ShellCommandRequest, credentials: ClusterCredentials = Depends(get_credentials)):
    try:
        return run_shell_command(credentials, payload.command, payload.cwd, payload.timeout)
    except Exception as exc:
        raise api_error(exc)


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
