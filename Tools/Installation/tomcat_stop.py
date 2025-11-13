import os
import subprocess
import time
from typing import Dict, Any
from .tool_base import Tool


class StopTomcat(Tool):
    """Stop Apache Tomcat server"""
    
    def __init__(self):
        super().__init__(
            name="stop_tomcat",
            description="Stop Apache Tomcat server",
            parameters={
                "tomcat_home": {
                    "type": "str",
                    "description": "Path to Tomcat installation directory (e.g., C:\\apache-tomcat\\apache-tomcat-10.1.34)"
                }
            }
        )
    
    def run(self, tomcat_home: str) -> Dict[str, Any]:
        """
        Stop Apache Tomcat server
        
        Args:
            tomcat_home: Path to Tomcat installation directory
        
        Returns:
            Dictionary with stop status and details
        """
        try:
            # Validate Tomcat home exists
            if not os.path.exists(tomcat_home):
                return {
                    "name": self.name,
                    "status": "Failed",
                    "command": "stop_tomcat",
                    "output": f"Tomcat directory not found: {tomcat_home}",
                    "details": f"Invalid TOMCAT_HOME: {tomcat_home}"
                }
            
            # Get shutdown script path
            bin_dir = os.path.join(tomcat_home, 'bin')
            if os.name == 'nt':  # Windows
                shutdown_script = os.path.join(bin_dir, 'shutdown.bat')
            else:  # Unix-like
                shutdown_script = os.path.join(bin_dir, 'shutdown.sh')
            
            if not os.path.exists(shutdown_script):
                return {
                    "name": self.name,
                    "status": "Failed",
                    "command": "stop_tomcat",
                    "output": f"Shutdown script not found: {shutdown_script}",
                    "details": "Invalid Tomcat installation - missing shutdown script"
                }
            
            # Stop Tomcat
            print(f"Stopping Tomcat at: {tomcat_home}")
            
            result = subprocess.run(
                [shutdown_script],
                cwd=bin_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Wait a moment for shutdown to complete
            time.sleep(2)
            
            output_msg = f"""
Tomcat shutdown initiated!

TOMCAT_HOME: {tomcat_home}
Shutdown Script: {shutdown_script}

Tomcat is shutting down.
Please wait a few seconds for complete shutdown.

Output: {result.stdout.strip() if result.stdout else 'Shutdown command executed'}
            """.strip()
            
            return {
                "name": self.name,
                "status": "Success",
                "command": f"Stop Tomcat at {tomcat_home}",
                "output": output_msg,
                "details": "Tomcat shutdown initiated successfully"
            }
            
        except subprocess.TimeoutExpired:
            return {
                "name": self.name,
                "status": "Failed",
                "command": "stop_tomcat",
                "output": "Shutdown command timed out after 30 seconds",
                "details": "Tomcat shutdown timed out"
            }
        except Exception as e:
            return {
                "name": self.name,
                "status": "Failed",
                "command": "stop_tomcat",
                "output": str(e),
                "details": f"Failed to stop Tomcat: {str(e)}"
            }


if __name__ == "__main__":
    # Test
    stopper = StopTomcat()
    result = stopper.run(tomcat_home="C:\\temp\\tomcat_test\\apache-tomcat-10.1.34")
    
    print(f"Status: {result['status']}")
    print(f"Details: {result['details']}")
    print(f"\n{result['output']}")
