from __future__ import annotations

import io
import json
import posixpath
import re
import secrets
import stat
from datetime import datetime, timezone
from pathlib import Path

from .database import record_job_event
from .sessions import ClusterCredentials
from .ssh_client import exec_inner, inner_client, sftp_inner


SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _python_here(script: str) -> str:
    return "python3 - <<'PY'\n" + script.strip() + "\nPY"


def exec_json(credentials: ClusterCredentials, script: str, timeout: int = 30):
    result = exec_inner(credentials, _python_here(script), timeout=timeout)
    if result.exit_status != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Remote command failed")
    return json.loads(result.stdout or "{}")


def get_health(credentials: ClusterCredentials) -> dict:
    script = r"""
import json, os, platform, subprocess
def run(cmd):
    try:
        return subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""
facts = {
    "hostname": platform.node() or run(["hostname"]),
    "username": run(["whoami"]),
    "home": os.path.expanduser("~"),
    "cwd": os.getcwd(),
    "os": run(["bash", "-lc", "cat /etc/centos-release 2>/dev/null || cat /etc/os-release 2>/dev/null | head -1"]),
    "cpu_count": os.cpu_count() or 0,
    "scheduler": {
        "squeue": bool(run(["bash", "-lc", "command -v squeue"])),
        "sacct": bool(run(["bash", "-lc", "command -v sacct"])),
        "qstat": bool(run(["bash", "-lc", "command -v qstat"])),
    },
}
print(json.dumps(facts))
"""
    return exec_json(credentials, script)


def get_login_health(credentials: ClusterCredentials) -> dict:
    cmd = r"""
printf 'hostname=%s\n' "$(hostname 2>/dev/null || true)"
printf 'username=%s\n' "$(whoami 2>/dev/null || true)"
printf 'home=%s\n' "$HOME"
printf 'cwd=%s\n' "$(pwd 2>/dev/null || true)"
printf 'os=%s\n' "$(cat /etc/centos-release 2>/dev/null || cat /etc/os-release 2>/dev/null | head -1 || true)"
printf 'cpu_count=%s\n' "$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || echo 0)"
if command -v squeue >/dev/null 2>&1; then printf 'scheduler_squeue=1\n'; else printf 'scheduler_squeue=0\n'; fi
if command -v sacct >/dev/null 2>&1; then printf 'scheduler_sacct=1\n'; else printf 'scheduler_sacct=0\n'; fi
if command -v qstat >/dev/null 2>&1; then printf 'scheduler_qstat=1\n'; else printf 'scheduler_qstat=0\n'; fi
"""
    result = exec_inner(credentials, cmd, timeout=20)
    if result.exit_status != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Remote login probe failed")
    values = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition("=")
        if key:
            values[key] = value
    try:
        cpu_count = int(values.get("cpu_count", "0"))
    except ValueError:
        cpu_count = 0
    return {
        "hostname": values.get("hostname", ""),
        "username": values.get("username", ""),
        "home": values.get("home", ""),
        "cwd": values.get("cwd", ""),
        "os": values.get("os", ""),
        "cpu_count": cpu_count,
        "scheduler": {
            "squeue": values.get("scheduler_squeue") == "1",
            "sacct": values.get("scheduler_sacct") == "1",
            "qstat": values.get("scheduler_qstat") == "1",
        },
    }


def get_metrics(credentials: ClusterCredentials) -> dict:
    script = r"""
import json, os, subprocess, time

def read_cpu():
    rows = []
    with open("/proc/stat", "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.startswith("cpu"):
                break
            parts = line.split()
            name = parts[0]
            values = [int(x) for x in parts[1:]]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            total = sum(values)
            rows.append((name, total, idle))
    return rows

def usage(a, b):
    out = []
    for (name, total1, idle1), (_, total2, idle2) in zip(a, b):
        dt = max(total2 - total1, 1)
        di = max(idle2 - idle1, 0)
        out.append({"name": name, "usage": round((1 - di / dt) * 100, 1)})
    return out

def meminfo():
    values = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as fh:
        for line in fh:
            key, rest = line.split(":", 1)
            values[key] = int(rest.strip().split()[0]) * 1024
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))
    used = max(total - available, 0)
    return {"total": total, "used": used, "available": available, "percent": round(used / total * 100, 1) if total else 0}

def disks():
    rows = []
    seen = set()
    try:
        out = subprocess.check_output(["df", "-P", "-B1", "/", os.path.expanduser("~")], universal_newlines=True)
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 6:
                continue
            fs, total, used, avail, pct, mount = parts[:6]
            if mount in seen:
                continue
            seen.add(mount)
            rows.append({"filesystem": fs, "mount": mount, "total": int(total), "used": int(used), "available": int(avail), "percent": float(pct.rstrip("%"))})
    except Exception:
        pass
    return rows

a = read_cpu()
time.sleep(0.25)
b = read_cpu()
cpu_rows = usage(a, b)
with open("/proc/loadavg", "r", encoding="utf-8") as fh:
    load = fh.read().split()[:3]
with open("/proc/uptime", "r", encoding="utf-8") as fh:
    uptime = float(fh.read().split()[0])
payload = {
    "timestamp": time.time(),
    "cpu": {"overall": cpu_rows[0]["usage"] if cpu_rows else 0, "cores": cpu_rows[1:]},
    "memory": meminfo(),
    "disks": disks(),
    "load": [float(x) for x in load],
    "uptime_seconds": uptime,
}
print(json.dumps(payload))
"""
    return exec_json(credentials, script)


def get_dashboard(credentials: ClusterCredentials, limit: int = 80) -> dict:
    script = rf"""
import json, os, signal, subprocess, time

def read_cpu():
    rows = []
    with open("/proc/stat", "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.startswith("cpu"):
                break
            parts = line.split()
            values = [int(x) for x in parts[1:]]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            rows.append((parts[0], sum(values), idle))
    return rows

def usage(a, b):
    out = []
    for (name, total1, idle1), (_, total2, idle2) in zip(a, b):
        dt = max(total2 - total1, 1)
        di = max(idle2 - idle1, 0)
        out.append({{"name": name, "usage": round((1 - di / dt) * 100, 1)}})
    return out

def meminfo():
    values = {{}}
    with open("/proc/meminfo", "r", encoding="utf-8") as fh:
        for line in fh:
            key, rest = line.split(":", 1)
            values[key] = int(rest.strip().split()[0]) * 1024
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))
    used = max(total - available, 0)
    return {{"total": total, "used": used, "available": available, "percent": round(used / total * 100, 1) if total else 0}}

def disks():
    rows = []
    seen = set()
    try:
        out = subprocess.check_output(["df", "-P", "-B1", "/", os.path.expanduser("~")], universal_newlines=True)
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 6:
                continue
            fs, total, used, avail, pct, mount = parts[:6]
            if mount in seen:
                continue
            seen.add(mount)
            rows.append({{"filesystem": fs, "mount": mount, "total": int(total), "used": int(used), "available": int(avail), "percent": float(pct.rstrip("%"))}})
    except Exception:
        pass
    return rows

def jobs():
    base = os.path.expanduser("~/.cluster_panel/jobs")
    rows = []
    def read(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read().strip()
        except Exception:
            return ""
    if os.path.isdir(base):
        for name in sorted(os.listdir(base), reverse=True):
            job_dir = os.path.join(base, name)
            if not os.path.isdir(job_dir):
                continue
            try:
                with open(os.path.join(job_dir, "meta.json"), "r", encoding="utf-8") as fh:
                    meta = json.load(fh)
            except Exception:
                meta = {{"id": name, "name": name}}
            pid_text = read(os.path.join(job_dir, "pid"))
            status = read(os.path.join(job_dir, "status")) or "unknown"
            alive = False
            if pid_text.isdigit():
                try:
                    os.kill(int(pid_text), 0)
                    alive = True
                except PermissionError:
                    alive = True
                except Exception:
                    alive = False
            if status in ("submitted", "running") and pid_text and not alive:
                status = "lost"
            meta.update({{
                "pid": pid_text,
                "status": status,
                "alive": alive,
                "started_at": read(os.path.join(job_dir, "started_at")),
                "ended_at": read(os.path.join(job_dir, "ended_at")),
                "exit_code": read(os.path.join(job_dir, "exit_code")),
            }})
            rows.append(meta)
    return rows[:200]

def tasks(limit, platform_pids):
    rows = []
    current_user = subprocess.check_output(["whoami"], universal_newlines=True).strip()
    system_users = set("root gdm dbus polkitd chrony avahi rtkit colord nobody".split())
    system_commands = set("systemd kthreadd sshd NetworkManager gsd-color gnome-shell dbus-daemon sftp-server rsyslogd tuned polkitd chronyd".split())
    skip_prefixes = ("/usr/libexec/", "/usr/sbin/", "/usr/bin/gnome", "/usr/bin/dbus", "[")
    compute_hints = ("julia", "matlab", "wolfram", "fortran", "ifort", "ifx", "gfortran", "mpirun", "mpiexec", "nohup", "run.sh", "./", ".out", ".x", "/home/", "/public/")
    internal_markers = ("cluster_panel", "<<'PY'", "read_cpu()", "/proc/meminfo", "python3 -", "python -")
    try:
        out = subprocess.check_output(["ps", "-eo", "pid,user,stat,pcpu,pmem,etimes,etime,comm,args", "--sort=-pcpu"], universal_newlines=True)
        for line in out.splitlines()[1:]:
            parts = line.split(None, 8)
            if len(parts) < 9:
                continue
            pid, user, status, cpu, mem, elapsed_seconds, elapsed, command, args = parts
            pid_int = int(pid)
            if pid_int in platform_pids:
                continue
            if user != current_user:
                continue
            cpu_value = float(cpu)
            args_lower = args.lower()
            if any(marker.lower() in args_lower for marker in internal_markers):
                continue
            if user in system_users or command in system_commands or args.startswith(skip_prefixes):
                continue
            if cpu_value <= 0.0 and not any(hint in args_lower for hint in compute_hints):
                continue
            try:
                cwd = os.readlink(f"/proc/{{pid_int}}/cwd")
            except Exception:
                cwd = ""
            rows.append({{
                "id": f"external-{{pid_int}}",
                "source": "external",
                "pid": pid_int,
                "user": user,
                "status": "running",
                "process_status": status,
                "cpu": cpu_value,
                "cpu_cores": round(cpu_value / 100.0, 2),
                "mem": float(mem),
                "elapsed_seconds": int(elapsed_seconds),
                "elapsed": elapsed,
                "command": command,
                "args": args,
                "name": command,
                "workdir": cwd,
                "alive": True,
            }})
            if len(rows) >= limit:
                break
    except Exception as exc:
        rows.append({{"error": str(exc)}})
    return rows

a = read_cpu()
time.sleep(0.25)
b = read_cpu()
cpu_rows = usage(a, b)
with open("/proc/loadavg", "r", encoding="utf-8") as fh:
    load = fh.read().split()[:3]
with open("/proc/uptime", "r", encoding="utf-8") as fh:
    up = float(fh.read().split()[0])
job_rows = jobs()
platform_pids = set()
for row in job_rows:
    pid_text = str(row.get("pid") or "")
    if pid_text.isdigit():
        platform_pids.add(int(pid_text))

payload = {{
    "metrics": {{
        "timestamp": time.time(),
        "cpu": {{"overall": cpu_rows[0]["usage"] if cpu_rows else 0, "cores": cpu_rows[1:]}},
        "memory": meminfo(),
        "disks": disks(),
        "load": [float(x) for x in load],
        "uptime_seconds": up,
    }},
    "jobs": job_rows,
    "processes": tasks({int(limit)}, platform_pids),
}}
print(json.dumps(payload, ensure_ascii=False))
"""
    return exec_json(credentials, script)


def get_processes(credentials: ClusterCredentials, limit: int = 80) -> dict:
    script = rf"""
import json, subprocess
limit = {int(limit)}
rows = []
system_users = set("root gdm dbus polkitd chrony avahi rtkit colord nobody".split())
system_commands = set("systemd kthreadd sshd NetworkManager gsd-color gnome-shell dbus-daemon sftp-server rsyslogd tuned polkitd chronyd".split())
skip_prefixes = ("/usr/libexec/", "/usr/sbin/", "/usr/bin/gnome", "/usr/bin/dbus", "[")
compute_hints = ("julia", "matlab", "wolfram", "fortran", "ifort", "ifx", "gfortran", "mpirun", "mpiexec", "nohup", "run.sh", "./", ".out", ".x", "/home/", "/public/")
internal_markers = ("cluster_panel", "<<'PY'", "read_cpu()", "/proc/meminfo", "python3 -", "python -")
try:
    out = subprocess.check_output(["ps", "-eo", "pid,user,stat,pcpu,pmem,etime,comm,args", "--sort=-pcpu"], universal_newlines=True)
    for line in out.splitlines()[1:]:
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        pid, user, status, cpu, mem, elapsed, command, args = parts
        cpu_value = float(cpu)
        args_lower = args.lower()
        if any(marker.lower() in args_lower for marker in internal_markers):
            continue
        if user in system_users:
            continue
        if command in system_commands:
            continue
        if args.startswith(skip_prefixes):
            continue
        if cpu_value <= 0.0 and not any(hint in args_lower for hint in compute_hints):
            continue
        rows.append({{"pid": int(pid), "user": user, "status": status, "cpu": cpu_value, "mem": float(mem), "elapsed": elapsed, "command": command, "args": args}})
        if len(rows) >= limit:
            break
except Exception as exc:
    rows.append({{"error": str(exc)}})
print(json.dumps({{"processes": rows}}))
"""
    return exec_json(credentials, script)


def kill_process(credentials: ClusterCredentials, pid: int, force: bool = False) -> dict:
    if pid <= 1:
        raise ValueError("Refuse to kill system pid")
    signal_name = "KILL" if force else "TERM"
    cmd = f"""
pid={int(pid)}
owner="$(ps -o user= -p "$pid" 2>/dev/null | awk '{{print $1}}')"
args="$(ps -o args= -p "$pid" 2>/dev/null | sed 's/^ *//')"
if [ -z "$owner" ]; then
  echo '{{"pid": {int(pid)}, "status": "not_found"}}'
  exit 0
fi
if kill -{signal_name} "$pid" 2>/tmp/cluster_panel_kill_err.$$; then
  sleep 0.5
  if kill -0 "$pid" 2>/dev/null; then
    alive=true
  else
    alive=false
  fi
  OWNER="$owner" ARGS="$args" ALIVE="$alive" SIGNAL="{signal_name}" python3 - <<'PY'
import json, os
print(json.dumps({{
    "pid": {int(pid)},
    "owner": os.environ.get("OWNER", ""),
    "args": os.environ.get("ARGS", ""),
    "signal": os.environ.get("SIGNAL", ""),
    "alive": os.environ.get("ALIVE") == "true",
    "status": "signaled",
}}))
PY
else
  err="$(cat /tmp/cluster_panel_kill_err.$$ 2>/dev/null)"
  rm -f /tmp/cluster_panel_kill_err.$$
  OWNER="$owner" ARGS="$args" ERR="$err" SIGNAL="{signal_name}" python3 - <<'PY'
import json, os
print(json.dumps({{
    "pid": {int(pid)},
    "owner": os.environ.get("OWNER", ""),
    "args": os.environ.get("ARGS", ""),
    "signal": os.environ.get("SIGNAL", ""),
    "status": "failed",
    "error": os.environ.get("ERR", ""),
}}))
PY
fi
rm -f /tmp/cluster_panel_kill_err.$$
"""
    result = exec_inner(credentials, cmd, timeout=15)
    if result.exit_status != 0:
        raise RuntimeError(result.stderr.strip() or "Failed to kill process")
    return json.loads(result.stdout or "{}")


LAUNCHER = r"""#!/usr/bin/env bash
set -u
job_dir="$1"
work_dir="$2"
cmd_file="$job_dir/command.sh"
mkdir -p "$job_dir"
nohup setsid bash -lc '
job_dir="$1"
work_dir="$2"
cmd_file="$3"
echo "$$" > "$job_dir/pid"
echo running > "$job_dir/status"
date -Is > "$job_dir/started_at"
exit_code=0
cd "$work_dir" || exit_code=98
if [ "$exit_code" -eq 0 ]; then
  bash "$cmd_file"
  exit_code=$?
fi
echo "$exit_code" > "$job_dir/exit_code"
if [ "$exit_code" -eq 0 ]; then
  echo finished > "$job_dir/status"
else
  echo failed > "$job_dir/status"
fi
date -Is > "$job_dir/ended_at"
' cluster_panel_runner "$job_dir" "$work_dir" "$cmd_file" > "$job_dir/stdout.log" 2> "$job_dir/stderr.log" < /dev/null &
pid=$!
echo "$pid" > "$job_dir/pid"
echo submitted > "$job_dir/status"
printf "%s\n" "$pid"
"""


def _mkdir_sftp(sftp, path: str) -> None:
    parts = []
    cur = path
    while cur not in ("", "/"):
        parts.append(cur)
        cur = posixpath.dirname(cur)
    for item in reversed(parts):
        try:
            sftp.stat(item)
        except OSError:
            sftp.mkdir(item)


def ensure_panel(credentials: ClusterCredentials) -> str:
    with inner_client(credentials) as ssh:
        sftp = ssh.open_sftp()
        try:
            home = sftp.normalize(".")
            base = posixpath.join(home, ".cluster_panel")
            _mkdir_sftp(sftp, posixpath.join(base, "jobs"))
            _mkdir_sftp(sftp, posixpath.join(base, "bin"))
            launcher_path = posixpath.join(base, "bin", "run_job.sh")
            with sftp.open(launcher_path, "w") as fh:
                fh.write(LAUNCHER)
            sftp.chmod(launcher_path, 0o700)
            return base
        finally:
            sftp.close()


def submit_job(credentials: ClusterCredentials, name: str, command: str, workdir: str) -> dict:
    base = ensure_panel(credentials)
    now = datetime.now(timezone.utc)
    job_id = now.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(4)
    job_dir = posixpath.join(base, "jobs", job_id)
    launcher_path = posixpath.join(base, "bin", "run_job.sh")
    metadata = {
        "id": job_id,
        "name": name.strip() or command.strip().splitlines()[0][:80],
        "command": command,
        "workdir": workdir,
        "created_by": credentials.username,
        "created_at": now.isoformat(),
    }
    with sftp_inner(credentials) as sftp:
        _mkdir_sftp(sftp, job_dir)
        with sftp.open(posixpath.join(job_dir, "command.sh"), "w") as fh:
            fh.write("#!/usr/bin/env bash\nset -e\n" + command.strip() + "\n")
        sftp.chmod(posixpath.join(job_dir, "command.sh"), 0o700)
        with sftp.open(posixpath.join(job_dir, "meta.json"), "w") as fh:
            fh.write(json.dumps(metadata, ensure_ascii=False, indent=2))
    cmd = f"{sh_quote(launcher_path)} {sh_quote(job_dir)} {sh_quote(workdir)}"
    result = exec_inner(credentials, cmd, timeout=20)
    if result.exit_status != 0:
        raise RuntimeError(result.stderr.strip() or "Failed to submit job")
    record_job_event(job_id, credentials.username, "submit", workdir, command)
    metadata["pid"] = result.stdout.strip()
    metadata["status"] = "submitted"
    return metadata


def list_jobs(credentials: ClusterCredentials) -> dict:
    script = r"""
import json, os, signal
base = os.path.expanduser("~/.cluster_panel/jobs")
jobs = []
def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read().strip()
    except Exception:
        return ""
if os.path.isdir(base):
    for name in sorted(os.listdir(base), reverse=True):
        job_dir = os.path.join(base, name)
        if not os.path.isdir(job_dir):
            continue
        try:
            with open(os.path.join(job_dir, "meta.json"), "r", encoding="utf-8") as fh:
                meta = json.load(fh)
        except Exception:
            meta = {"id": name, "name": name}
        pid_text = read(os.path.join(job_dir, "pid"))
        status = read(os.path.join(job_dir, "status")) or "unknown"
        alive = False
        if pid_text.isdigit():
            try:
                os.kill(int(pid_text), 0)
                alive = True
            except PermissionError:
                alive = True
            except ProcessLookupError:
                alive = False
            except Exception:
                alive = False
        if status in ("submitted", "running") and pid_text and not alive:
            status = "lost"
        meta.update({
            "pid": pid_text,
            "status": status,
            "alive": alive,
            "started_at": read(os.path.join(job_dir, "started_at")),
            "ended_at": read(os.path.join(job_dir, "ended_at")),
            "exit_code": read(os.path.join(job_dir, "exit_code")),
            "stdout_size": os.path.getsize(os.path.join(job_dir, "stdout.log")) if os.path.exists(os.path.join(job_dir, "stdout.log")) else 0,
            "stderr_size": os.path.getsize(os.path.join(job_dir, "stderr.log")) if os.path.exists(os.path.join(job_dir, "stderr.log")) else 0,
        })
        jobs.append(meta)
print(json.dumps({"jobs": jobs[:200]}, ensure_ascii=False))
"""
    return exec_json(credentials, script)


def stop_job(credentials: ClusterCredentials, job_id: str) -> dict:
    if not SAFE_JOB_ID.match(job_id):
        raise ValueError("Invalid job id")
    cmd = f"""
job_dir="$HOME/.cluster_panel/jobs/{job_id}"
pid="$(cat "$job_dir/pid" 2>/dev/null || true)"
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  sleep 0.8
  kill -KILL -- "-$pid" 2>/dev/null || true
fi
echo killed > "$job_dir/status"
date -Is > "$job_dir/ended_at"
printf '%s' "$pid"
"""
    result = exec_inner(credentials, cmd, timeout=15)
    if result.exit_status != 0:
        raise RuntimeError(result.stderr.strip() or "Failed to stop job")
    record_job_event(job_id, credentials.username, "stop")
    return {"id": job_id, "pid": result.stdout.strip(), "status": "killed"}


def get_job_logs(credentials: ClusterCredentials, job_id: str, stream: str = "stdout", limit: int = 60000) -> dict:
    if not SAFE_JOB_ID.match(job_id):
        raise ValueError("Invalid job id")
    filename = "stderr.log" if stream == "stderr" else "stdout.log"
    cmd = f"tail -c {int(limit)} \"$HOME/.cluster_panel/jobs/{job_id}/{filename}\" 2>/dev/null || true"
    result = exec_inner(credentials, cmd, timeout=15)
    return {"id": job_id, "stream": stream, "text": result.stdout}


def normalize_remote_path(sftp, path: str | None) -> str:
    home = sftp.normalize(".")
    if not path or path in ("~", ""):
        return home
    if path.startswith("~/"):
        return posixpath.join(home, path[2:])
    if not path.startswith("/"):
        return posixpath.normpath(posixpath.join(home, path))
    return posixpath.normpath(path)


def list_files(credentials: ClusterCredentials, path: str | None) -> dict:
    with sftp_inner(credentials) as sftp:
        remote_path = normalize_remote_path(sftp, path)
        attrs = sftp.listdir_attr(remote_path)
        items = []
        for attr in sorted(attrs, key=lambda x: (not stat.S_ISDIR(x.st_mode), x.filename.lower())):
            items.append(
                {
                    "name": attr.filename,
                    "path": posixpath.join(remote_path, attr.filename),
                    "is_dir": stat.S_ISDIR(attr.st_mode),
                    "size": attr.st_size,
                    "mtime": attr.st_mtime,
                    "mode": oct(attr.st_mode & 0o777),
                }
            )
        return {"path": remote_path, "parent": posixpath.dirname(remote_path), "items": items}


def read_text_file(credentials: ClusterCredentials, path: str, limit: int = 200000) -> dict:
    with sftp_inner(credentials) as sftp:
        remote_path = normalize_remote_path(sftp, path)
        with sftp.open(remote_path, "rb") as fh:
            data = fh.read(limit)
        return {"path": remote_path, "text": data.decode("utf-8", errors="replace"), "truncated": len(data) >= limit}


def run_shell_command(credentials: ClusterCredentials, command: str, cwd: str | None = None, timeout: int = 120) -> dict:
    command = command.rstrip()
    if not command:
        return {"stdout": "", "stderr": "", "exit_status": 0, "cwd": cwd or "~"}
    marker = "__CLUSTER_PANEL_DONE_" + secrets.token_hex(8) + "__"
    start_dir = cwd or "~"
    script = "\n".join(
        [
            f"cd {sh_quote(start_dir)} 2>/dev/null || cd ~",
            command,
            "_cluster_panel_status=$?",
            f"printf '\\n{marker}%s:%s\\n' \"$_cluster_panel_status\" \"$(pwd)\"",
            "exit $_cluster_panel_status",
        ]
    )
    result = exec_inner(credentials, f"bash -lc {sh_quote(script)}", timeout=timeout)
    stdout = result.stdout
    exit_status = result.exit_status
    next_cwd = start_dir
    marker_pos = stdout.rfind(marker)
    if marker_pos >= 0:
        body = stdout[:marker_pos]
        meta = stdout[marker_pos + len(marker) :].strip().splitlines()[0] if stdout[marker_pos + len(marker) :].strip() else ""
        status_text, _, cwd_text = meta.partition(":")
        try:
            exit_status = int(status_text)
        except ValueError:
            exit_status = result.exit_status
        if cwd_text:
            next_cwd = cwd_text.strip()
        stdout = body.rstrip("\n")
    return {
        "stdout": stdout,
        "stderr": result.stderr,
        "exit_status": exit_status,
        "cwd": next_cwd,
    }


def upload_file(credentials: ClusterCredentials, directory: str, filename: str, content) -> dict:
    with sftp_inner(credentials) as sftp:
        remote_dir = normalize_remote_path(sftp, directory)
        remote_path = posixpath.join(remote_dir, posixpath.basename(filename))
        sftp.putfo(content, remote_path)
        attr = sftp.stat(remote_path)
        return {"path": remote_path, "size": attr.st_size}


def download_file_stream(credentials: ClusterCredentials, path: str):
    filename = posixpath.basename(path.rstrip("/")) or "download"

    def iterator():
        with sftp_inner(credentials) as sftp:
            remote_path = normalize_remote_path(sftp, path)
            with sftp.open(remote_path, "rb") as fh:
                while True:
                    chunk = fh.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk

    return filename, iterator()


def delete_path(credentials: ClusterCredentials, path: str) -> dict:
    with sftp_inner(credentials) as sftp:
        remote_path = normalize_remote_path(sftp, path)
        attr = sftp.stat(remote_path)
        if stat.S_ISDIR(attr.st_mode):
            sftp.rmdir(remote_path)
        else:
            sftp.remove(remote_path)
        return {"path": remote_path, "deleted": True}


def rename_path(credentials: ClusterCredentials, old_path: str, new_name: str) -> dict:
    safe_name = posixpath.basename(new_name.strip())
    if not safe_name or safe_name in (".", ".."):
        raise ValueError("Invalid new name")
    with sftp_inner(credentials) as sftp:
        remote_old = normalize_remote_path(sftp, old_path)
        remote_new = posixpath.join(posixpath.dirname(remote_old), safe_name)
        sftp.rename(remote_old, remote_new)
        return {"old_path": remote_old, "new_path": remote_new}


def mkdir_path(credentials: ClusterCredentials, parent: str, name: str) -> dict:
    safe_name = posixpath.basename(name.strip())
    if not safe_name or safe_name in (".", ".."):
        raise ValueError("Invalid directory name")
    with sftp_inner(credentials) as sftp:
        remote_parent = normalize_remote_path(sftp, parent)
        remote_path = posixpath.join(remote_parent, safe_name)
        sftp.mkdir(remote_path)
        return {"path": remote_path}
