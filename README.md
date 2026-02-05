# VPS-SSH-Wrapper

Lightweight Python SSH client and CLI for remote VPS administration, designed for both human operators and AI assistants.

## Description

### Features

- **Persistent SSH Connections** with automatic reconnection and health checks
- **Secure Credentials** via `.env` files (password or key-based auth)
- **Unified CLI** (`vps cmd`, `vps shell`, `vps put`, `vps get`)
- **File Transfer** (upload/download files and directories via SFTP with progress bars)
- **Python API** (`PersistentSSH` class for embedding in scripts)
- **Thread-Safe** (internal locking for concurrent command execution)
- **Error-Resilient** (retries failed commands after reconnecting)

### Installation

```bash
git clone https://github.com/fabiopauli/ssh-wrapper.git
cd ssh-wrapper
pip install -e .
```

After install, the `vps` command is available system-wide.

You can also run scripts directly without installing:
```bash
python main.py cmd "df -h"
python vps_cmd.py "df -h"
```

### Setup Credentials (.env)

Copy `.env_example` to `.env` and edit your values:

```
login=username@your-vps-hostname.com
password=your-strong-password
```

**SSH key auth (recommended):** Place your private key file in the `./keys/` directory and reference it by filename:

```
login=username@your-vps-hostname.com
SSH_KEY_FILE=id_rsa
```

The key path resolves to `./keys/id_rsa`. When `SSH_KEY_FILE` is set, password can be omitted.

Never commit `.env` to git -- it is already in `.gitignore`.

### CLI Usage

```bash
# Run a single command
vps cmd "df -h"
vps cmd --timeout 60 "sudo systemctl restart nginx"

# Interactive shell (exit with 'exit' or Ctrl+C)
vps shell

# Upload file or directory
vps put ./backup.sql /home/user/backups/backup.sql
vps put ./my-app/ /home/user/apps/my-app/

# Download file or directory
vps get /var/log/nginx/access.log ./logs/access.log
vps get /home/user/configs/ ./backup-configs/

# Quiet mode (suppress progress bars)
vps put -q ./large-file.tar.gz /home/user/large-file.tar.gz
```

### Python API Reference

```python
from ssh_util import PersistentSSH

ssh = PersistentSSH(
    hostname="your-vps.example.com",
    username="user",
    password="pass",        # or omit if using key
    key_filename="./keys/id_rsa",  # or omit if using password
    port=22
)
```

| Method | Description | Returns |
|--------|-------------|---------|
| `connect()` | Establish SSH connection (called automatically by `__init__`). | `None` |
| `is_connected()` | Check if connection is alive. | `bool` |
| `execute(command, timeout=30)` | Run command with auto-reconnect and retry. | `{'output': str, 'error': str, 'exit_status': int}` |
| `reconnect()` | Force reconnect. | `None` |
| `close()` | Close SSH and SFTP connections. | `None` |
| `get_sftp()` | Get SFTP client (lazy-initialized). | `paramiko.SFTPClient` |
| `put(local, remote, callback)` | Upload a file. | `{'success': bool, 'error': str, 'bytes_transferred': int}` |
| `get(remote, local, callback)` | Download a file. | `{'success': bool, 'error': str, 'bytes_transferred': int}` |
| `put_dir(local_dir, remote_dir, callback)` | Upload directory recursively. | `{'success': bool, 'files_transferred': int, 'total_bytes': int, 'failed_files': list}` |
| `get_dir(remote_dir, local_dir, callback)` | Download directory recursively. | `{'success': bool, 'files_transferred': int, 'total_bytes': int, 'failed_files': list}` |

### Project Structure

```
ssh-wrapper/
├── keys/                # SSH private keys (gitignored)
├── ssh_util.py          # Core PersistentSSH class
├── vps_cmd.py           # Standalone single-command script
├── vps_shell.py         # Standalone interactive shell script
├── main.py              # Unified CLI entrypoint (vps cmd/shell/put/get)
├── .env_example         # Example credentials file
├── requirements.txt
├── pyproject.toml
└── README.md
```

### Troubleshooting

- **Connection fails**: Verify `login` format is `user@host`, check firewall rules and SSH port.
- **Permission denied**: Use `sudo` in commands, or switch to SSH key auth.
- **Interactive commands hang**: Use `vps shell` for tools like `htop`, `vim`, etc.
- **Command timeouts**: Increase timeout with `--timeout` flag or `timeout=` parameter.
- **Reconnection loops**: Check network stability and VPS availability.

### Security Best Practices

- Prefer SSH keys over passwords. Place keys in `./keys/` and set `SSH_KEY_FILE` in `.env`.
- Never hardcode credentials -- always use `.env`.
- Disable root login on your VPS; use sudoers for privilege escalation.
- Enable Fail2Ban on your VPS to block brute-force attempts.
- Monitor `/var/log/auth.log` for suspicious activity.

---

## For AI Assistants

This section is for AI agents (Claude Code, etc.) that use this tool to execute commands on a remote VPS.

### What this tool does for you

VPS-SSH-Wrapper lets you run shell commands on a remote server and get structured output back. It handles SSH connection management, reconnection, and credential loading automatically.

### Setup (prerequisites before use)

Before you can use this tool, the user must have:

1. Installed the package: `pip install -e .` (from the project root)
2. Created a `.env` file with at minimum `login=user@host` and either `password=...` or `SSH_KEY_FILE=keyname` (with the key in `./keys/`)
3. Verified connectivity: `vps cmd "echo ok"`

### Primary tool: vps_cmd.py

For non-interactive command execution, use `vps_cmd.py`. It loads credentials from `.env` automatically.

**Syntax:**
```bash
python vps_cmd.py "command to run"
```

**Output format:**
- **stdout**: Command output printed to stdout
- **stderr**: Error output printed to stderr
- **exit code**: The process exits with the remote command's exit code

**Examples:**
```bash
# Check disk space
python vps_cmd.py "df -h"

# Check running services
python vps_cmd.py "systemctl status nginx"

# View recent logs
python vps_cmd.py "tail -n 50 /var/log/nginx/error.log"

# Check system resources
python vps_cmd.py "free -h && uptime"

# Run multiple commands
python vps_cmd.py "apt update && apt list --upgradable"
```

**Interpreting results:**
- Exit code `0` means success.
- Non-zero exit code means the command failed. Check stderr for details.
- If the connection itself fails, an error is printed to stderr and exit code is `1`.

### File transfer

Use the installed CLI for file transfers:

```bash
# Upload
vps put <local_path> <remote_path>

# Download
vps get <remote_path> <local_path>
```

Both support files and directories. Add `-q` for quiet mode (no progress output).

### Output format reference

When using the Python API (`ssh.execute()`), the return value is a dict:

```python
{
    'output': str,      # stdout from the command
    'error': str,       # stderr from the command
    'exit_status': int  # exit code (0 = success)
}
```

File transfer methods return:

```python
# Single file (put/get)
{'success': bool, 'error': str | None, 'bytes_transferred': int}

# Directory (put_dir/get_dir)
{'success': bool, 'error': str | None, 'files_transferred': int, 'total_bytes': int, 'failed_files': list}
```

---

## License

MIT License
