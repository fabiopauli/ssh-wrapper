#!/usr/bin/env python3
"""
Unified CLI for VPS SSH Wrapper.
Usage:
  python main.py cmd [--timeout 300] "your command"
  python main.py shell
Or install: pip install -e .  # then `vps cmd "df -h"`
"""

import argparse
import os
import sys
import select
import time
from dotenv import load_dotenv
from ssh_util import PersistentSSH

load_dotenv()

def get_ssh():
    login = os.getenv('login')
    password = os.getenv('password')
    key_file = os.getenv('SSH_KEY_FILE')
    if not login:
        print("Error: 'login' (username@host) required in .env", file=sys.stderr)
        sys.exit(1)
    username, hostname = login.split('@', 1)
    key_filename = f"./keys/{key_file}" if key_file else None
    ssh_conn = PersistentSSH(
        hostname=hostname,
        username=username,
        password=password,
        key_filename=key_filename
    )
    return ssh_conn

def cmd(args):
    ssh = get_ssh()
    try:
        command = ' '.join(args.command)
        result = ssh.execute(command, timeout=args.timeout)
        if result['output']:
            print(result['output'], end='')
        if result['error']:
            print(result['error'], file=sys.stderr, end='')
        sys.exit(result['exit_status'])
    finally:
        ssh.close()

def interactive_shell(ssh_conn):
    channel = ssh_conn.ssh.invoke_shell()
    channel.settimeout(0.1)
    print("=== VPS Interactive Shell (type 'exit' or Ctrl+C) ===")
    try:
        while True:
            if channel.recv_ready():
                output = channel.recv(4096).decode('utf-8', errors='ignore')
                sys.stdout.write(output)
                sys.stdout.flush()
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                user_input = sys.stdin.readline()
                if user_input.strip().lower() == 'exit':
                    break
                channel.send(user_input)
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        channel.close()

def shell(args):
    ssh = get_ssh()
    try:
        interactive_shell(ssh)
    finally:
        ssh.close()
        print("\nConnection closed.")

def cli():
    parser = argparse.ArgumentParser(description="VPS SSH Wrapper", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    subparsers = parser.add_subparsers(dest='subcommand', required=True)
    
    # cmd
    cmd_p = subparsers.add_parser('cmd', help='Run single command')
    cmd_p.add_argument('command', nargs='+', help='Command to execute')
    cmd_p.add_argument('--timeout', type=int, default=300, help='Command timeout (s)')
    
    # shell
    subparsers.add_parser('shell', help='Interactive shell')
    
    args = parser.parse_args()
    
    if args.subcommand == 'cmd':
        cmd(args)
    elif args.subcommand == 'shell':
        shell(args)

if __name__ == "__main__":
    cli()