import os
import shutil
from typing import Dict, Any

from .tool_base import Tool
# class Tool:
#     def __init__(self, name, description, parameters):
#         self.name = name
#         self.description = description
#         self.parameters = parameters

    # def run(self):
    #     raise NotImplementedError


class CheckDisk(Tool):
    def __init__(self):
        super().__init__(
            name="check_disk",
            description="Check available disk space on the main drive",
            parameters={
                "min_free_mb": {
                    "type": "int",
                    "description": "Minimum required free space in MB (default: 250 MB)",
                },
                "path": {
                    "type": "str",
                    "description": "Path to check disk space (default: root of main drive)",
                }
            }
        )

    def _get_disk_usage(self, path: str = "/") -> Dict[str, float]:
        """Return total, used, and free space in bytes for the given path."""
        usage = shutil.disk_usage(path)
        return {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
        }

    def run(self, min_free_mb: int = 250, path: str = "C:\\") -> Dict[str, Any]:
        try:
            usage = self._get_disk_usage(path)

            free_mb = usage["free"] / (1024 * 1024)
            total_mb = usage["total"] / (1024 * 1024)
            used_mb = usage["used"] / (1024 * 1024)

            space_available = "Yes" if free_mb >= min_free_mb else "No"

            details = (
                f"Drive: {path}\n"
                f"Total: {total_mb:.2f} MB\n"
                f"Used: {used_mb:.2f} MB\n"
                f"Free: {free_mb:.2f} MB\n"
            )

            recommendation = ""
            if free_mb < min_free_mb:
                recommendation = (
                    f"Free space is below the required {min_free_mb} MB.\n"
                    "Consider cleaning temporary files or freeing up disk space before installing Tomcat."
                )

            return {
                "name": self.name,
                "space available": space_available,
                "command": f"disk_usage({path})",
                "output": details,
                "details": f"Free space: {free_mb:.2f} MB (Threshold: {min_free_mb} MB)", 
                "metrics": {
                    "total_mb": round(total_mb, 2),
                    "used_mb": round(used_mb, 2),
                    "free_mb": round(free_mb, 2),
                },
                
            }

        except Exception as e:
            return {
                "name": self.name,
                "status": "Failed",
                "command": "shutil.disk_usage()", 
            }


# if __name__ == "__main__":
#     tool = CheckDisk()
#     # Example: run with default 250 MB threshold
#     result = tool.run(250,"C:\\")
#     print("=== Disk Space Check ===")
#     for k, v in result.items():
#         print(f"{k}: {v}\n")
