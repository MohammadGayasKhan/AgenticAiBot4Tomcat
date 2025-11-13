import os
import re
import subprocess
import sys
from typing import Dict, Any
from .tool_base import Tool

# class Tool:
#     """Base class for all prerequisite check tools.

#     Subclasses must implement run() and return a dictionary with the required
#     keys described in the project requirements.
#     """
#     def __init__(self, name, description, parameters):
#         self.name: str = name
#         self.description: str = description
#         self.parameters: list = parameters

#     def get_info(self) -> Dict[str, Any]:
#         return {
#             "description": self.description,
#             "parameters": self.parameters,
#         }

    # def run(self):
    #     raise NotImplementedError



class CheckJava(Tool):

    def __init__(self):
        # Tool base expects (name, description, parameters)
        super().__init__(
            name="check_java",
            description="Check java installation, versions and JAVA_HOME",
            parameters=[]
        )

    def parse_java_major(self, version_text: str) -> int:
        """Parse Java major version from typical `java -version` output.

        Examples:
        openjdk version "17.0.2" -> 17
        java version "1.8.0_351" -> 8
        Returns 0 if not found or unparseable.
        """
        if not version_text:
            return 0

        m = re.search(r'"?(\d+)(?:[\.\-](\d+))?', version_text)
        if not m:
            return 0
        major = int(m.group(1)) 
        if major == 1 and m.group(2):
            try:
                return int(m.group(2))
            except Exception:
                return 0
        return major

    def run(self) -> Dict[str, Any]:
        try:
            cmd = ["java", "-version"]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            java_out = (proc.stdout or proc.stderr or "").strip()

            javac_proc = subprocess.run(["javac", "-version"], capture_output=True, text=True)
            javac_out = (javac_proc.stdout or javac_proc.stderr or "").strip()

            java_major = self.parse_java_major(java_out + "\n" + javac_out)

            status = "Success" if java_major >= 11 else "Failed"

            details = f"Detected Java major version: {java_major}." 

            return {
                "name": self.name,
                "status": status    ,
                "command": "java -version; javac -version; env JAVA_HOME",
                "output": java_out + ("\n" + javac_out if javac_out else ""),
                "details": details,
            }

        except Exception as e: 
            return {
                "name": self.name,
                "status": status,
                "command": "java -version",
                "output": "",
                "details": f"Exception while checking Java: \n{'='*15}\n{e}", 
            }


# if __name__ == "__main__":
#     tool = CheckJava()
#     result = tool.run()
#     for i,j in result.items():
#         print(f"{i}: {j}")