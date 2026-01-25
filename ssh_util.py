import paramiko
import time
import os
from threading import Lock
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class PersistentSSH:
    def __init__(self, hostname, username, password=None, key_filename=None, port=22):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.port = port
        self.ssh = None
        self.lock = Lock()
        self.connect()
    
    def connect(self):
        """Establish SSH connection"""
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.key_filename:
                self.ssh.connect(
                    hostname=self.hostname,
                    port=self.port,
                    username=self.username,
                    key_filename=self.key_filename,
                    timeout=10
                )
            else:
                self.ssh.connect(
                    hostname=self.hostname,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=10
                )
            print(f"Connected to {self.hostname}")
        except Exception as e:
            print(f"Connection failed: {e}")
            raise
    
    def is_connected(self):
        """Check if connection is still alive"""
        if self.ssh is None:
            return False
        try:
            transport = self.ssh.get_transport()
            if transport is None or not transport.is_active():
                return False
            transport.send_ignore()
            return True
        except:
            return False
    
    def reconnect(self):
        """Reconnect if connection is lost"""
        print("Reconnecting...")
        self.close()
        time.sleep(2)
        self.connect()
    
    def execute(self, command, timeout=30):
        """Execute a command with automatic reconnection"""
        with self.lock:
            if not self.is_connected():
                self.reconnect()
            
            try:
                stdin, stdout, stderr = self.ssh.exec_command(command, timeout=timeout)
                output = stdout.read().decode('utf-8')
                error = stderr.read().decode('utf-8')
                exit_status = stdout.channel.recv_exit_status()
                
                return {
                    'output': output,
                    'error': error,
                    'exit_status': exit_status
                }
            except Exception as e:
                print(f"Command execution failed: {e}")
                # Try to reconnect and retry once
                self.reconnect()
                stdin, stdout, stderr = self.ssh.exec_command(command, timeout=timeout)
                output = stdout.read().decode('utf-8')
                error = stderr.read().decode('utf-8')
                exit_status = stdout.channel.recv_exit_status()
                
                return {
                    'output': output,
                    'error': error,
                    'exit_status': exit_status
                }
    
    def close(self):
        """Close the SSH connection"""
        if self.ssh:
            self.ssh.close()
            self.ssh = None

# Usage example
if __name__ == "__main__":
    # Load credentials from .env file
    login = os.getenv('login')  # Format: username@hostname
    password = os.getenv('password')

    if not login or not password:
        print("Error: login and password must be set in .env file")
        exit(1)

    # Parse login (format: username@hostname)
    if '@' in login:
        username, hostname = login.split('@', 1)
    else:
        print("Error: login format should be 'username@hostname'")
        exit(1)

    # Initialize connection
    ssh_conn = PersistentSSH(
        hostname=hostname,
        username=username,
        password=password,
        port=22
    )

    try:
        # Execute multiple commands without reconnecting
        result1 = ssh_conn.execute('pwd')
        print("Current directory:", result1['output'])

        result2 = ssh_conn.execute('ls -la')
        print("Directory listing:", result2['output'])

        result3 = ssh_conn.execute('uptime')
        print("Uptime:", result3['output'])

        # Keep the connection alive
        print("\nConnection remains open for future commands...")

    except KeyboardInterrupt:
        print("\nClosing connection...")
        ssh_conn.close()