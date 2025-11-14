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

    def run(self, command):
        stdin, stdout, stderr = self.client.exec_command(command)
        return stdout.read().decode(), stderr.read().decode()

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
