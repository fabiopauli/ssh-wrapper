#!/usr/bin/env python3
import os
import sys
import select
import time
from dotenv import load_dotenv
from ssh_util import PersistentSSH

def interactive_shell(ssh_conn):
    """Open an interactive shell session"""
    channel = ssh_conn.ssh.invoke_shell()
    channel.settimeout(0.1)

    print("Interactive VPS shell started. Type 'exit' to close.")
    print("=" * 60)

    try:
        while True:
            # Check if there's output from the server
            if channel.recv_ready():
                output = channel.recv(4096).decode('utf-8', errors='ignore')
                sys.stdout.write(output)
                sys.stdout.flush()

            # Check if there's input from user
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                command = sys.stdin.readline()
                if command.strip().lower() == 'exit':
                    break
                channel.send(command)

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n\nShell interrupted.")
    finally:
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
