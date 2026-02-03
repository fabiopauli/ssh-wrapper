#!/usr/bin/env python3
"""
Unified CLI for VPS SSH Wrapper.
Usage:
  python main.py cmd [--timeout 300] "your command"
  python main.py shell
  python main.py put <local> <remote>
  python main.py get <remote> <local>
Or install: pip install -e .  # then `vps cmd "df -h"`
"""

import argparse
import os
import sys
import select
import stat
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


def create_progress_callback(description="Transferring"):
    """Create a progress callback for file transfers"""
    last_percent = [-1]

    def callback(transferred, total):
        if total > 0:
            percent = int(transferred * 100 / total)
            if percent != last_percent[0]:
                last_percent[0] = percent
                bar_len = 40
                filled = int(bar_len * transferred / total)
                bar = '=' * filled + '-' * (bar_len - filled)
                size_mb = total / (1024 * 1024)
                transferred_mb = transferred / (1024 * 1024)
                sys.stdout.write(f'\r{description}: [{bar}] {percent}% ({transferred_mb:.1f}/{size_mb:.1f} MB)')
                sys.stdout.flush()
                if percent == 100:
                    sys.stdout.write('\n')

    return callback


def create_dir_progress_callback():
    """Create a progress callback for directory transfers"""
    def callback(current_file, transferred, total):
        if total > 0:
            percent = int(transferred * 100 / total)
            filename = os.path.basename(current_file)
            if len(filename) > 30:
                filename = filename[:27] + '...'
            sys.stdout.write(f'\r{filename}: {percent}%   ')
            sys.stdout.flush()
            if percent == 100:
                sys.stdout.write('\n')

    return callback


def put_command(args):
    """Handle 'vps put' command"""
    ssh = get_ssh()
    try:
        local_path = args.local
        remote_path = args.remote

        if os.path.isdir(local_path):
            print(f"Uploading directory: {local_path} -> {remote_path}")
            callback = create_dir_progress_callback() if not args.quiet else None
            result = ssh.put_dir(local_path, remote_path, callback=callback)

            if result['success']:
                print(f"Successfully uploaded {result['files_transferred']} files ({result['total_bytes']} bytes)")
                sys.exit(0)
            else:
                print(f"Upload completed with errors: {result['error']}", file=sys.stderr)
                for f in result['failed_files']:
                    print(f"  Failed: {f['file']} - {f['error']}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Uploading file: {local_path} -> {remote_path}")
            callback = create_progress_callback("Uploading") if not args.quiet else None
            result = ssh.put(local_path, remote_path, callback=callback)

            if result['success']:
                print(f"Successfully uploaded {result['bytes_transferred']} bytes")
                sys.exit(0)
            else:
                print(f"Upload failed: {result['error']}", file=sys.stderr)
                sys.exit(1)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        ssh.close()


def get_command(args):
    """Handle 'vps get' command"""
    ssh = get_ssh()
    try:
        remote_path = args.remote
        local_path = args.local

        sftp = ssh.get_sftp()
        try:
            remote_stat = sftp.stat(remote_path)
            is_dir = stat.S_ISDIR(remote_stat.st_mode)
        except IOError:
            print(f"Error: Remote path not found: {remote_path}", file=sys.stderr)
            sys.exit(1)

        if is_dir:
            print(f"Downloading directory: {remote_path} -> {local_path}")
            callback = create_dir_progress_callback() if not args.quiet else None
            result = ssh.get_dir(remote_path, local_path, callback=callback)

            if result['success']:
                print(f"Successfully downloaded {result['files_transferred']} files ({result['total_bytes']} bytes)")
                sys.exit(0)
            else:
                print(f"Download completed with errors: {result['error']}", file=sys.stderr)
                for f in result['failed_files']:
                    print(f"  Failed: {f['file']} - {f['error']}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Downloading file: {remote_path} -> {local_path}")
            callback = create_progress_callback("Downloading") if not args.quiet else None
            result = ssh.get(remote_path, local_path, callback=callback)

            if result['success']:
                print(f"Successfully downloaded {result['bytes_transferred']} bytes")
                sys.exit(0)
            else:
                print(f"Download failed: {result['error']}", file=sys.stderr)
                sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        ssh.close()


def cli():
    parser = argparse.ArgumentParser(description="VPS SSH Wrapper", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    subparsers = parser.add_subparsers(dest='subcommand', required=True)
    
    # cmd
    cmd_p = subparsers.add_parser('cmd', help='Run single command')
    cmd_p.add_argument('command', nargs='+', help='Command to execute')
    cmd_p.add_argument('--timeout', type=int, default=300, help='Command timeout (s)')
    
    # shell
    subparsers.add_parser('shell', help='Interactive shell')

    # put
    put_p = subparsers.add_parser('put', help='Upload file or directory to remote')
    put_p.add_argument('local', help='Local file or directory path')
    put_p.add_argument('remote', help='Remote destination path')
    put_p.add_argument('-q', '--quiet', action='store_true', help='Suppress progress output')

    # get
    get_p = subparsers.add_parser('get', help='Download file or directory from remote')
    get_p.add_argument('remote', help='Remote file or directory path')
    get_p.add_argument('local', help='Local destination path')
    get_p.add_argument('-q', '--quiet', action='store_true', help='Suppress progress output')

    args = parser.parse_args()

    if args.subcommand == 'cmd':
        cmd(args)
    elif args.subcommand == 'shell':
        shell(args)
    elif args.subcommand == 'put':
        put_command(args)
    elif args.subcommand == 'get':
        get_command(args)

if __name__ == "__main__":
    cli()