import os
import urllib.request
import zipfile
import subprocess
from typing import Dict, Any
from .tool_base import Tool
 
 
class JavaInstallTool(Tool):
    """
    Automatically downloads and installs OpenJDK,
    sets JAVA_HOME and updates PATH dynamically.
    """
 
    def __init__(self, version="17", arch="x64"):
        super().__init__(
            name="install_java",
            description="Download and install OpenJDK dynamically, set JAVA_HOME and PATH",
            parameters=[
                {"name": "version", "default": version},
                {"name": "arch", "default": arch},
            ],
        )
        self.version = version
        self.arch = arch
 
    def run(self) -> Dict[str, Any]:
        logs = []
        status = "Failed"
 
        try:
            home = os.path.expanduser("~")
            java_root = os.path.join(home, "Java")
            os.makedirs(java_root, exist_ok=True)
 
            zip_path = os.path.join(home, "Downloads", "jdk.zip")
            url = (
                f"https://aka.ms/download-jdk/"
                f"microsoft-jdk-{self.version}-windows-{self.arch}.zip"
            )
 
            logs.append(f"Downloading JDK from: {url}")
            urllib.request.urlretrieve(url, zip_path)
            logs.append(f"Downloaded to: {zip_path}")
 
            logs.append("Extracting...")
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(java_root)
 
            # Find extracted folder dynamically
            jdk_folder = None
            for name in os.listdir(java_root):
                if name.startswith("jdk"):
                    jdk_folder = name
                    break
 
            if not jdk_folder:
                raise Exception("JDK folder not found after extraction!")
 
            jdk_path = os.path.join(java_root, jdk_folder)
            bin_path = os.path.join(jdk_path, "bin")
 
            logs.append(f"Detected JDK folder: {jdk_path}")
 
            # Set JAVA_HOME
            os.environ["JAVA_HOME"] = jdk_path
            subprocess.run(
                ["powershell", "-Command",
                 f'[Environment]::SetEnvironmentVariable("JAVA_HOME", "{jdk_path}", "User")']
            )
            logs.append(f"JAVA_HOME set to {jdk_path}")
 
            # Update PATH dynamically (prepend)
            subprocess.run(
                [
                    "powershell", "-Command",
                    f'''
                    $old = [Environment]::GetEnvironmentVariable("PATH","User");
                    if ($old -notlike "*{bin_path.replace("\\", "\\\\")}*") {{
                        $new = "{bin_path};" + $old;
                        [Environment]::SetEnvironmentVariable("PATH",$new,"User");
                    }}
                    '''
                ]
            )
            logs.append("PATH updated with JDK bin directory")
 
            # Test installation
            test = subprocess.run(
                [os.path.join(bin_path, "java.exe"), "-version"],
                capture_output=True,
                text=True
            )
 
            output = test.stdout + test.stderr
 
            if "version" in output.lower():
                status = "Success"
            else:
                status = "Failed"
 
            return {
                "name": self.name,
                "status": status,
                "command": "java -version",
                "output": output.strip(),
                "details": "\n".join(logs),
            }
 
        except Exception as e:
            logs.append(f"Exception: {e}")
            return {
                "name": self.name,
                "status": "Failed",
                "command": "java -version",
                "output": "",
                "details": "\n".join(logs),
            }
 