<div align="center">
  <img src="assets/quantum-icon.png" alt="Cluster Management Platform: Quantum logo" width="150">
  <h1>Cluster Management Platform: Quantum</h1>
  <p><strong>Quantum Cluster / Server Console</strong></p>
  <p>A lightweight, open-source, native Windows SSH management tool for Linux servers and small clusters</p>
  <p>
    <a href="./README.md">中文</a> | English
  </p>
  <p>
    <a href="https://github.com/Jiangsese/cluster-management-platform-quantum/releases/latest"><img alt="version" src="https://img.shields.io/github/v/release/Jiangsese/cluster-management-platform-quantum?label=version&style=flat-square&color=2f80ed"></a>
    <a href="./LICENSE"><img alt="license" src="https://img.shields.io/github/license/Jiangsese/cluster-management-platform-quantum?label=license&style=flat-square&color=2ea44f"></a>
    <img alt="platform" src="https://img.shields.io/badge/platform-Windows-0078D4?style=flat-square">
    <img alt="Python" src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white">
    <img alt="UI" src="https://img.shields.io/badge/UI-PySide6-41CD52?style=flat-square">
    <img alt="SSH" src="https://img.shields.io/badge/SSH-Paramiko-2F4858?style=flat-square">
    <img alt="AI assisted" src="https://img.shields.io/badge/AI%20Assisted-Codex-6f42c1?style=flat-square">
  </p>
</div>

---

A lightweight, open-source, native Windows SSH management tool for Linux servers and small clusters. It is built for small Linux servers, lab clusters, shared workstations, and personal remote compute nodes that do not have Slurm/PBS or a full web portal.

Quantum is just a name here. It does not mean this project has anything fancy to do with quantum computing ^^.

The application opens as a local desktop window, not a browser wrapper. It does not connect to any server by default, and it does not include any built-in cluster address, username, password, or private key.

## Features

- Multiple cluster profiles: save a separate name, connection mode, host settings, username, and optional password for each cluster.
- Direct SSH: use this when the target server is reachable from your local machine.
- Bastion SSH: use this when you must first log in to a jump host before reaching an internal compute node.
- Resource overview: view CPU, memory, disk, load, uptime, and basic node information.
- Lightweight job management: no Slurm/PBS dependency and no root permission required.
- External task detection: show compute processes launched by the same Linux user from other SSH clients or scripts.
- Real stop buttons: both managed jobs and visible external tasks can be stopped from the UI.
- File management: browse remote files over SFTP, upload, download, preview text files, rename, delete files, and remove empty directories.
- Command panel: run ordinary Linux commands such as `pwd`, `ls -lh`, `cd project`, and `tail out.txt`.
- Optional local password saving: when `记住账号和密码` is enabled, passwords are protected with the current Windows user's data protection mechanism.

## Download

Download the Windows package from GitHub Releases:

```text
QuantumClusterConsole-windows-x64.zip
```

Extract it and run:

```text
量子集群服务器控制台.exe
```

Keep the whole extracted folder together. Do not copy only the single exe file, because the application also needs the runtime files next to it.

## Screenshots

Login and multi-cluster profiles:

![Login and multi-cluster profiles](docs/images/login.png)

Resource overview and task detection:

![Resource overview and task detection](docs/images/dashboard.png)

File management and text preview:

![File management and text preview](docs/images/file-management.png)

## Quick Start

1. Open the application.
2. Click `新建` and give the cluster a name, for example `A集群`.
3. Choose `直接连接` or `跳板机方式`.
4. Fill in the host address, SSH port, Linux username, and password.
5. If you want the application to auto-fill the credentials next time, enable `记住账号和密码`, then save the cluster.
6. Click `登录` to enter the console.

## Connection Modes

Direct connection:

```text
Local Windows PC -> Linux server
```

Bastion mode:

```text
Local Windows PC -> Bastion host -> Internal compute node
```

Use direct connection if the target server is reachable from your local machine. Use bastion mode if the compute node is inside a private network and must be reached through a jump host.

## Jobs

This tool does not depend on Slurm/PBS. Commands submitted from the `作业` page are tracked by a lightweight user-level registry on the remote machine:

```text
~/.cluster_panel/
```

The job table shows two kinds of tasks:

- `平台`: tasks submitted through this application, with status tracking, stdout/stderr logs, and stop actions.
- `外部`: compute processes launched by the same Linux user from another SSH client, `nohup`, or scripts. These show PID, approximate CPU cores, elapsed time, working directory, and a stop action.

External tasks do not always expose stdout/stderr to the platform. If their output has been redirected to a file, use the file page or command panel to inspect it.

## Command Panel

The command panel is meant for ordinary shell commands. Commands are executed through the current SSH session, and the current directory is preserved after `cd`.

Good examples:

```bash
pwd
ls -lh
cd project
tail -n 50 out.txt
```

It is not a full PTY terminal. Full-screen interactive tools such as `vim`, `top`, `htop`, and `less` are not recommended. For long-running computations, use the job page or run a background command yourself:

```bash
nohup python run.py > out.txt 2>&1 &
```

## Security Statement

- No built-in server address, username, password, or private key.
- The current application is a local desktop program and does not expose passwords through a web frontend.
- Password saving is disabled by default.
- Saved passwords are stored only under the current Windows user context.
- No sudo required.
- No remote system service is installed.
- Remote files change only when the user explicitly uploads, renames, deletes, or creates something.

## Run From Source

```powershell
git clone https://github.com/Jiangsese/cluster-management-platform-quantum.git
cd cluster-management-platform-quantum
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run_dev.ps1
```

## Build Windows Package

```powershell
.\build_exe.ps1
```

The packaged application is generated under:

```text
dist\量子集群服务器控制台\量子集群服务器控制台.exe
```

## Source Layout

- `native_app.py`: native PySide6 desktop UI.
- `backend/app/ssh_client.py`: direct and bastion SSH connection layer.
- `backend/app/remote.py`: remote metrics, jobs, files, command panel, and process actions.
- `backend/app/sessions.py`: credential and session data structures.
- `backend/app/config.py`: application paths and defaults.
- `assets/`: application icon and background assets.
- `tests/`: unit tests.

## Tests

```powershell
python -m pytest -q
```

## License

MIT License.

## Note

This project originally started as a visual management entry and platform for a small research-group server. Later it turned out that, with some generalization, it could become a reusable SSH cluster/server console, so it is released here as open source. Anyone can freely modify and use it.

The visual design and icons mainly relied on image2, and most of the underlying logic was optimized with help from Codex.
