import os
import re
import subprocess
from typing import Dict, Any, List
from .tool_base import Tool

# class Tool:
#     def __init__(self, name, description, parameters):
#         self.name = name
#         self.description = description
#         self.parameters = parameters
#     def run(self):
#         raise NotImplementedError

class CheckPorts(Tool):
    def __init__(self):
        super().__init__(
            name="check_ports",
            description="Check ports and report owning processes",
            parameters={"ports": "list of int"}
        )

    def _run_cmd(self, cmd: List[str]) -> str:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return (proc.stdout or proc.stderr or "").strip()

    def run(self, ports: List[int] = [8080, 8005, 8009]) -> Dict[str, Any]: 

        if os.name != "nt":
            return {
                "name": self.name,
                "status": "Failed",
                "command": "netstat -ano",
                "output": "This tool targets Windows (netstat & tasklist required).",
                "details": "",
            }

        netstat_out = self._run_cmd(["netstat", "-ano"])
        lines = netstat_out.splitlines()

        summary_lines: List[str] = []
        overall_ok = True

        for port in ports:
            matches = []
            for line in lines:
                s = re.sub(r"\s+", " ", line).strip()
                if not s:
                    continue
                # match :<port> followed by space or end of address field (not \b which can cause false matches)
                if re.search(rf":{port}(?:\s|$)", s):
                    pid = s.split()[-1] if s.split() and s.split()[-1].isdigit() else None
                    matches.append((s, pid))

            if not matches:
                summary_lines.append(f"Port {port}: free")
                continue

            overall_ok = False
            summary_lines.append(f"Port {port}: IN USE ({len(matches)} match(es))")
            for net_line, pid in matches:
                summary_lines.append(f"  netstat: {net_line}")
                if pid:
                    task_out = self._run_cmd(["tasklist", "/FI", f"PID eq {pid}"])
                    # include tasklist output indented
                    task_lines = task_out.splitlines()
                    if task_lines:
                        summary_lines.append("  tasklist:")
                        for t in task_lines:
                            summary_lines.append(f"    {t}")
                    else:
                        summary_lines.append("  tasklist: (no info)")
                else:
                    summary_lines.append("  tasklist: PID not found in netstat line")

        status = "Success" if overall_ok else "Failed"
        combined_output = "\n".join(summary_lines)

        return {
            "name": self.name,
            "status": status,
            "command": "netstat -ano ; tasklist /FI \"PID eq <pid>\"",
            "output": combined_output,
            "details": "Ports checked: " + ", ".join(str(p) for p in ports),
        }

# if __name__ == "__main__":
#     tool = CheckPorts()
#     # example: include Ollama port 11434 and default 8080
#     ports=list(map(int,input().split()))
#     result = tool.run(ports) 
#     print(result["output"])
