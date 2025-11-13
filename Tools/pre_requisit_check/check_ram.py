import platform
import re
import subprocess
from typing import Dict, Any


# Local Tool base (matches structure used in check_java)
class Tool:
    def __init__(self, name, description, parameters):
        self.name: str = name
        self.description: str = description
        self.parameters: list = parameters

    def get_info(self) -> Dict[str, Any]:
        return {"description": self.description, "parameters": self.parameters}

    def run(self):
        raise NotImplementedError


class CheckRAM(Tool):
    def __init__(self):
        super().__init__(name="check_ram", description="Check physical RAM available", parameters=[])

    def run(self) -> Dict[str, Any]:
        try:
            sys_plat = platform.system().lower()
            total_mb = 0
            output = ""
            if sys_plat.startswith("windows"):
                proc = subprocess.run(["wmic", "computersystem", "get", "TotalPhysicalMemory"], capture_output=True, text=True)
                output = proc.stdout.strip()
                m = re.search(r"(\d+)", output)
                if m:
                    total_bytes = int(m.group(1))
                    # Convert bytes to MB: bytes / 1024 / 1024
                    total_mb = int(total_bytes / (1024 * 1024))
            elif sys_plat.startswith("darwin"):
                proc = subprocess.run(["sysctl", "hw.memsize"], capture_output=True, text=True)
                output = proc.stdout.strip()
                m = re.search(r"(\d+)", output)
                if m:
                    total_bytes = int(m.group(1))
                    # Convert bytes to MB: bytes / 1024 / 1024
                    total_mb = int(total_bytes / (1024 * 1024))
            else:
                # Linux: free -m already returns values in MB
                proc = subprocess.run(["free", "-m"], capture_output=True, text=True)
                output = proc.stdout.strip()
                for line in output.splitlines():
                    if line.lower().startswith("mem:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            total_mb = int(parts[1])
                        break

            status = "Success" if total_mb >= 512 else "Failed"
            details = f"Total physical memory: {total_mb} MB. Minimum required: 512 MB, recommended: 2048 MB+."

            return {
                "name": self.name,
                "status": status,
                "command": "wmic computersystem get TotalPhysicalMemory | sysctl hw.memsize | free -m",
                "output": output,
                "details": details,
                "metrics": {"total_mb": total_mb},
            }

        except Exception as e:
            return {
                "name": self.name,
                "status": "Failed",
                "command": "free -m or wmic ...",
                "output": "",
                "details": f"Exception while checking RAM: {e}",
            }
