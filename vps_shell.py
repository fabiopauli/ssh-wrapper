#!/usr/bin/env python3
import os
import sys
import select
import signal
import struct
import termios
import tty
from dotenv import load_dotenv
from ssh_util import PersistentSSH


def _get_terminal_size():
    """Get terminal dimensions (cols, rows)."""
    try:
        import fcntl
        s = struct.pack('HHHH', 0, 0, 0, 0)
        result = struct.unpack('HHHH',
                               fcntl.ioctl(sys.stdout.fileno(),
                                           termios.TIOCGWINSZ, s))
        return result[1], result[0]  # cols, rows
    except Exception:
        return 80, 24


def interactive_shell(ssh_conn):
    """Open an interactive shell session with full raw terminal support."""
    cols, rows = _get_terminal_size()
    term = os.environ.get('TERM', 'xterm-256color')
    channel = ssh_conn.ssh.invoke_shell(term=term, width=cols, height=rows)

    # Handle terminal resize
    def sigwinch_handler(signum, frame):
        c, r = _get_terminal_size()
        try:
            channel.resize_pty(width=c, height=r)
        except Exception:
            pass

    old_settings = termios.tcgetattr(sys.stdin)
    old_sigwinch = signal.getsignal(signal.SIGWINCH)

    try:
        tty.setraw(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
        channel.settimeout(0.0)
        signal.signal(signal.SIGWINCH, sigwinch_handler)

        while True:
            r, w, e = select.select([channel, sys.stdin], [], [])

            if channel in r:
                try:
                    data = channel.recv(4096)
                    if len(data) == 0:
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                except Exception:
                    break

            if sys.stdin in r:
                data = os.read(sys.stdin.fileno(), 1024)
                if len(data) == 0:
                    break
                channel.send(data)

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        signal.signal(signal.SIGWINCH, old_sigwinch)
        channel.close()

def execute_command(ssh_conn, command):
    """Execute a single command and return results"""
    result = ssh_conn.execute(command)

    if result['output']:
        print(result['output'], end='')
    if result['error']:
        print(result['error'], file=sys.stderr, end='')

    return result['exit_status']

if __name__ == "__main__":
    # Load credentials
    load_dotenv()
    login = os.getenv('login')
    password = os.getenv('password')
    key_file = os.getenv('SSH_KEY_FILE')
    key_filename = None
    if key_file:
        key_path = os.path.join('keys', key_file)
        if os.path.exists(key_path):
            key_filename = key_path
        else:
            print(f"Error: SSH key file '{key_path}' not found.", file=sys.stderr)
            sys.exit(1)
    if not login or (password is None and key_filename is None):
        print("Error: 'login' must be set, and either 'password' or 'SSH_KEY_FILE' (pointing to existing file in keys/) must be set in .env file", file=sys.stderr)
        sys.exit(1)
    username, hostname = login.split('@', 1)

    # Connect
    ssh_conn = PersistentSSH(
        hostname=hostname,
        username=username,
        password=password,
        key_filename=key_filename,
        port=22
    )

    try:
        if len(sys.argv) > 1:
            # Single command mode
            command = ' '.join(sys.argv[1:])
            exit_code = execute_command(ssh_conn, command)
            sys.exit(exit_code)
        else:
            # Interactive mode
            interactive_shell(ssh_conn)

    finally:
        ssh_conn.close()
        print("\nConnection closed.")
