# VPS-SSH-Wrapper
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight Python library and CLI tools for secure SSH access to remote VPS instances. Designed specifically for integration with local AI CLI agents (like Grok Engineer, Claude, etc.) to enable remote server administration via natural language commands.

## 🚀 Features

- **Persistent SSH Connections**: Automatic reconnection and connection health checks.
- **Secure Credentials**: Uses `.env` files for passwords/keys (supports both password and key-based auth).
- **CLI Tools**:
  - `main.py` (or `vps` after `pip install -e .`): Unified CLI - `vps cmd "command"`, `vps shell`, `vps put`, `vps get`
  - Legacy: `vps_cmd.py`, `vps_shell.py` (direct scripts)
- **File Transfer**: Upload/download files and directories via SFTP with progress display.
- **Python API**: Simple class for embedding in scripts/tools.
- **Thread-Safe**: Uses locks for concurrent command execution.
- **Error-Resilient**: Retries on failures with reconnection.
- **Examples Included**: Security scans, log checks, resource monitoring.

Perfect for AI agents to run shell commands on your VPS without exposing raw SSH keys or managing sessions manually.

## 📦 Installation

1. **Clone/Download** this repository:
   ```bash
   git clone https://github.com/fabiopauli/ssh-wrapper.git
   cd ssh-wrapper
   ```

2. **Install Dependencies & CLI**:
   ```bash
   # Core deps
   pip install -r requirements.txt
   
   # Editable install for `vps` CLI command (recommended)
   pip install -e .
   
   # Or uv (faster)
   uv pip install -r requirements.txt -e .
   ```
   Now use `vps cmd "df -h"` or `python main.py cmd "df -h"`

3. **Setup Credentials** (create `.env` in project root):
   ```
   login=username@your-vps-hostname.com
   password=your-strong-password
   ```
   - **Pro Tip**: For production, use SSH keys instead:
     ```
     login=username@your-vps-hostname.com
     # password= (omit)
     ```
     Pass `key_filename="/path/to/private_key"` to `PersistentSSH`.

   ⚠️ **Security Warning**: Never commit `.env` to git! Add it to `.gitignore`. Prefer SSH keys over passwords.

## ⚡ Quick Start

### 1. Single Command (CLI)
```bash
# Installed CLI
vps cmd "df -h"
vps cmd --timeout 60 "sudo systemctl restart nginx"

# Or direct
python main.py cmd "df -h"

# Interactive cmds better with shell
vps shell  # then htop
```

### 2. Interactive Shell
```bash
# Installed CLI
vps shell

# Or direct
python main.py shell
```
- Full TTY shell. `exit` or Ctrl+C to quit. Tab-completion, history supported.

### 3. File Transfer
```bash
# Upload a file
vps put ./backup.sql /home/user/backups/backup.sql

# Download a file
vps get /var/log/nginx/access.log ./logs/access.log

# Upload a directory (recursive)
vps put ./my-app/ /home/user/apps/my-app/

# Download a directory (recursive)
vps get /home/user/configs/ ./backup-configs/

# Quiet mode (no progress bar)
vps put -q ./large-file.tar.gz /home/user/large-file.tar.gz
```

### 4. Python Scripts
```python
from dotenv import load_dotenv
from ssh_util import PersistentSSH
import os

load_dotenv()
login = os.getenv('login')
password = os.getenv('password')
if '@' not in login:
    raise ValueError("login format: username@hostname")

username, hostname = login.split('@', 1)

ssh = PersistentSSH(hostname=hostname, username=username, password=password, key_filename=None)  # or key_filename="./keys/id_rsa.pem"
try:
    result = ssh.execute("uptime", timeout=10)
    print("Output:", result['output'])
    print("Errors:", result['error'])
    print("Exit Code:", result['exit_status'])
finally:
    ssh.close()
```

## 🛠 API Reference

### `PersistentSSH(hostname, username, password=None, key_filename=None, port=22)`

| Method | Description | Returns |
|--------|-------------|---------|
| `connect()` | Establishes SSH connection (called in `__init__`). | None |
| `is_connected()` | Checks connection liveness. | `bool` |
| `execute(command, timeout=30)` | Runs command with auto-reconnect/retry. | `dict`: `{'output': str, 'error': str, 'exit_status': int}` |
| `reconnect()` | Force reconnect. | None |
| `close()` | Closes connection. | None |
| `get_sftp()` | Returns SFTP client (lazy init). | `paramiko.SFTPClient` |
| `put(local, remote, callback)` | Upload file. | `dict`: `{'success': bool, 'error': str, 'bytes_transferred': int}` |
| `get(remote, local, callback)` | Download file. | `dict`: `{'success': bool, 'error': str, 'bytes_transferred': int}` |
| `put_dir(local_dir, remote_dir, callback)` | Upload directory recursively. | `dict`: `{'success': bool, 'files_transferred': int, 'total_bytes': int, 'failed_files': list}` |
| `get_dir(remote_dir, local_dir, callback)` | Download directory recursively. | `dict`: `{'success': bool, 'files_transferred': int, 'total_bytes': int, 'failed_files': list}` |

- **Thread-Safe**: Use in multi-threaded apps (internal `Lock`).
- **Timeouts**: Custom per-command.
- **Encoding**: UTF-8 stdout/stderr.

### Common Admin Tasks
```bash
# Logs
vps cmd "tail -f -n 100 /var/log/nginx/error.log"

# Services
vps cmd "systemctl status nginx && systemctl status postgresql"

# Resources
vps cmd "df -h && free -h && ps aux --sort=-%mem | head -10"

# Updates
vps cmd "apt update && apt upgrade -y"
```


## 🤖 AI Agent Integration

This wrapper is ideal for tools like Grok CLI or Claude Code:

1. Add `vps_cmd.py` execution to agent tools.
2. Agent can run: `python vps_cmd.py "command"` via shell tools.
3. Parse `output`/`error`/`exit_status` for decisions.

Example agent tool prompt: "Use `vps_cmd.py` to check server status before deploying."

## 🐛 Troubleshooting

- **Connection Fails**: Verify `login` format, firewall, SSH port.
- **Permission Denied**: Use `sudo` in commands if needed (may prompt for password—use keys!).
- **Interactive Commands Fail**: Use `vps_shell.py` for `htop`, `vim`, etc.
- **Timeouts**: Increase `timeout` in `execute()`.
- **Reconnection Loops**: Check network stability.

## 📁 Project Structure
```
ssh-wrapper/
├── keys/                # SSH private keys (optional)
├── ssh_util.py          # Core SSH class
├── vps_cmd.py           # Single-command CLI
├── vps_shell.py         # Interactive shell CLI
├── main.py              # Unified CLI entrypoint (vps cmd/shell)
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 🔒 Security Best Practices
- **SSH Keys**: Preferred over passwords.
- **No Root Login**: Use sudoers for privilege escalation.
- **Fail2Ban**: Enable on VPS to block brute-force.
- **Audit Logs**: Monitor `/var/log/auth.log`.
- **Environment**: Never hardcode creds—always `.env`.


## 📄 License
MIT License

## 🙏 Acknowledgments
Built with [Paramiko](https://www.paramiko.org/) for SSH.

---

*Made for AI-powered DevOps!*
