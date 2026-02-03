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
        self.sftp = None
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
    
    def get_sftp(self):
        """Get or create SFTP client with auto-reconnection"""
        if not self.is_connected():
            self.reconnect()

        if self.sftp is not None:
            try:
                self.sftp.stat('.')
            except Exception:
                self.sftp = None

        if self.sftp is None:
            self.sftp = self.ssh.open_sftp()

        return self.sftp

    def put(self, local_path, remote_path, callback=None):
        """
        Upload a single file to remote server.

        Args:
            local_path: Local file path
            remote_path: Remote destination path
            callback: Optional progress callback(bytes_transferred, total_bytes)

        Returns:
            dict: {'success': bool, 'error': str or None, 'bytes_transferred': int}
        """
        local_path = os.path.expanduser(local_path)
        if not os.path.isfile(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")

        file_size = os.path.getsize(local_path)

        with self.lock:
            try:
                sftp = self.get_sftp()
                sftp.put(local_path, remote_path, callback=callback)
                return {
                    'success': True,
                    'error': None,
                    'bytes_transferred': file_size
                }
            except IOError as e:
                return {
                    'success': False,
                    'error': str(e),
                    'bytes_transferred': 0
                }
            except Exception as e:
                self.sftp = None
                self.reconnect()
                sftp = self.get_sftp()
                sftp.put(local_path, remote_path, callback=callback)
                return {
                    'success': True,
                    'error': None,
                    'bytes_transferred': file_size
                }

    def get(self, remote_path, local_path, callback=None):
        """
        Download a single file from remote server.

        Args:
            remote_path: Remote file path
            local_path: Local destination path
            callback: Optional progress callback(bytes_transferred, total_bytes)

        Returns:
            dict: {'success': bool, 'error': str or None, 'bytes_transferred': int}
        """
        local_path = os.path.expanduser(local_path)

        local_dir = os.path.dirname(local_path)
        if local_dir and not os.path.exists(local_dir):
            os.makedirs(local_dir)

        with self.lock:
            try:
                sftp = self.get_sftp()
                file_stat = sftp.stat(remote_path)
                file_size = file_stat.st_size
                sftp.get(remote_path, local_path, callback=callback)
                return {
                    'success': True,
                    'error': None,
                    'bytes_transferred': file_size
                }
            except IOError as e:
                return {
                    'success': False,
                    'error': str(e),
                    'bytes_transferred': 0
                }
            except Exception as e:
                self.sftp = None
                self.reconnect()
                sftp = self.get_sftp()
                file_stat = sftp.stat(remote_path)
                sftp.get(remote_path, local_path, callback=callback)
                return {
                    'success': True,
                    'error': None,
                    'bytes_transferred': file_stat.st_size
                }

    def put_dir(self, local_dir, remote_dir, callback=None):
        """
        Upload a directory recursively to remote server.

        Args:
            local_dir: Local directory path
            remote_dir: Remote destination directory
            callback: Optional progress callback(current_file, bytes_transferred, total_bytes)

        Returns:
            dict: {'success': bool, 'error': str or None,
                   'files_transferred': int, 'total_bytes': int, 'failed_files': list}
        """
        import stat

        local_dir = os.path.expanduser(local_dir)
        if not os.path.isdir(local_dir):
            raise NotADirectoryError(f"Local directory not found: {local_dir}")

        files_transferred = 0
        total_bytes = 0
        failed_files = []

        with self.lock:
            sftp = self.get_sftp()

            def mkdir_p(remote_directory):
                if remote_directory == '/':
                    return
                try:
                    sftp.stat(remote_directory)
                except IOError:
                    dirname = os.path.dirname(remote_directory)
                    if dirname:
                        mkdir_p(dirname)
                    sftp.mkdir(remote_directory)

            try:
                mkdir_p(remote_dir)
            except Exception as e:
                return {
                    'success': False,
                    'error': f"Failed to create remote directory: {e}",
                    'files_transferred': 0,
                    'total_bytes': 0,
                    'failed_files': []
                }

            for root, dirs, files in os.walk(local_dir):
                rel_path = os.path.relpath(root, local_dir)
                if rel_path == '.':
                    current_remote_dir = remote_dir
                else:
                    current_remote_dir = os.path.join(remote_dir, rel_path).replace('\\', '/')

                for d in dirs:
                    remote_subdir = os.path.join(current_remote_dir, d).replace('\\', '/')
                    try:
                        mkdir_p(remote_subdir)
                    except Exception:
                        pass

                for f in files:
                    local_file = os.path.join(root, f)
                    remote_file = os.path.join(current_remote_dir, f).replace('\\', '/')

                    try:
                        file_size = os.path.getsize(local_file)

                        if callback:
                            def file_callback(transferred, total, lf=local_file):
                                callback(lf, transferred, total)
                            sftp.put(local_file, remote_file, callback=file_callback)
                        else:
                            sftp.put(local_file, remote_file)

                        files_transferred += 1
                        total_bytes += file_size
                    except Exception as e:
                        failed_files.append({'file': local_file, 'error': str(e)})

        return {
            'success': len(failed_files) == 0,
            'error': None if len(failed_files) == 0 else f"{len(failed_files)} files failed",
            'files_transferred': files_transferred,
            'total_bytes': total_bytes,
            'failed_files': failed_files
        }

    def get_dir(self, remote_dir, local_dir, callback=None):
        """
        Download a directory recursively from remote server.

        Args:
            remote_dir: Remote directory path
            local_dir: Local destination directory
            callback: Optional progress callback(current_file, bytes_transferred, total_bytes)

        Returns:
            dict: {'success': bool, 'error': str or None,
                   'files_transferred': int, 'total_bytes': int, 'failed_files': list}
        """
        import stat

        local_dir = os.path.expanduser(local_dir)
        files_transferred = 0
        total_bytes = 0
        failed_files = []

        with self.lock:
            sftp = self.get_sftp()

            try:
                remote_stat = sftp.stat(remote_dir)
                if not stat.S_ISDIR(remote_stat.st_mode):
                    return {
                        'success': False,
                        'error': f"Remote path is not a directory: {remote_dir}",
                        'files_transferred': 0,
                        'total_bytes': 0,
                        'failed_files': []
                    }
            except IOError:
                return {
                    'success': False,
                    'error': f"Remote directory not found: {remote_dir}",
                    'files_transferred': 0,
                    'total_bytes': 0,
                    'failed_files': []
                }

            os.makedirs(local_dir, exist_ok=True)

            def download_recursive(remote_path, local_path):
                nonlocal files_transferred, total_bytes, failed_files

                for entry in sftp.listdir_attr(remote_path):
                    remote_entry = os.path.join(remote_path, entry.filename).replace('\\', '/')
                    local_entry = os.path.join(local_path, entry.filename)

                    if stat.S_ISDIR(entry.st_mode):
                        os.makedirs(local_entry, exist_ok=True)
                        download_recursive(remote_entry, local_entry)
                    else:
                        try:
                            if callback:
                                def file_callback(transferred, total, rf=remote_entry):
                                    callback(rf, transferred, total)
                                sftp.get(remote_entry, local_entry, callback=file_callback)
                            else:
                                sftp.get(remote_entry, local_entry)

                            files_transferred += 1
                            total_bytes += entry.st_size
                        except Exception as e:
                            failed_files.append({'file': remote_entry, 'error': str(e)})

            download_recursive(remote_dir, local_dir)

        return {
            'success': len(failed_files) == 0,
            'error': None if len(failed_files) == 0 else f"{len(failed_files)} files failed",
            'files_transferred': files_transferred,
            'total_bytes': total_bytes,
            'failed_files': failed_files
        }

    def close(self):
        """Close the SSH and SFTP connections"""
        if self.sftp:
            try:
                self.sftp.close()
            except Exception:
                pass
            self.sftp = None
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