import time
import paramiko

class RemoteExecutor:
    def __init__(self, host, username, password=None, key_path=None):
        self.host = host
        self.username = username
        self.password = password
        self.key_path = key_path
        self.client = None

    def connect(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if self.key_path:
            key = paramiko.RSAKey.from_private_key_file(self.key_path)
            self.client.connect(self.host, username=self.username, pkey=key)
        else:
            self.client.connect(self.host, username=self.username, password=self.password)

    def run(self, command, timeout=None):
        if not self.client:
            raise RuntimeError("RemoteExecutor is not connected")

        transport = self.client.get_transport()
        if not transport:
            raise RuntimeError("SSH transport is not available")

        channel = transport.open_session()
        if timeout and timeout > 0:
            channel.settimeout(timeout)

        channel.exec_command(command)
        stdout_chunks = []
        stderr_chunks = []
        start_time = time.time()

        while True:
            while channel.recv_ready():
                stdout_chunks.append(channel.recv(4096))
            while channel.recv_stderr_ready():
                stderr_chunks.append(channel.recv_stderr(4096))

            if channel.exit_status_ready():
                break

            if timeout and timeout > 0 and (time.time() - start_time) > timeout:
                channel.close()
                raise TimeoutError(f"Remote command timed out after {timeout} seconds")

            time.sleep(0.1)

        exit_status = channel.recv_exit_status()
        while channel.recv_ready():
            stdout_chunks.append(channel.recv(4096))
        while channel.recv_stderr_ready():
            stderr_chunks.append(channel.recv_stderr(4096))

        channel.close()

        stdout_data = b"".join(stdout_chunks).decode(errors="replace")
        stderr_data = b"".join(stderr_chunks).decode(errors="replace")

        if exit_status != 0 and not stderr_data:
            stderr_data = f"Command exited with status {exit_status}"

        return stdout_data, stderr_data

    def detect_os(self):
        # Linux check
        out, _ = self.run("uname")
        if "Linux" in out:
            return "linux"

        # Windows check
        out, _ = self.run("powershell \"(Get-WmiObject Win32_OperatingSystem).Caption\"")
        if out.strip():
            return "windows"

        return "unknown"

    def close(self):
        self.client.close()
