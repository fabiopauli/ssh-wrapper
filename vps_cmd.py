#!/usr/bin/env python3
"""
Simple command wrapper for VPS administration.
Usage: python vps_cmd.py "command to run"
"""
import os
import sys
from dotenv import load_dotenv
from ssh_util import PersistentSSH

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
    # Get command from arguments
    if len(sys.argv) < 2:
        print("Usage: python vps_cmd.py 'command'", file=sys.stderr)
        sys.exit(1)

    command = ' '.join(sys.argv[1:])

    # Execute
    result = ssh_conn.execute(command, timeout=300)

    # Output results
    if result['output']:
        print(result['output'], end='')
    if result['error']:
        print(result['error'], file=sys.stderr, end='')

    sys.exit(result['exit_status'])

finally:
    ssh_conn.close()
