import os
import subprocess
import time
from typing import Dict, Any
from .tool_base import Tool


class StartTomcat(Tool):
    """Start Apache Tomcat server"""
    
    def __init__(self):
        super().__init__(
            name="start_tomcat",
            description="Start Apache Tomcat server",
            parameters={
                "tomcat_home": {
                    "type": "str",
                    "description": "Path to Tomcat installation directory (e.g., C:\\apache-tomcat\\apache-tomcat-10.1.34)"
                }
            }
        )
    
    def run(self, tomcat_home: str) -> Dict[str, Any]:
        """
        Start Apache Tomcat server
        
        Args:
            tomcat_home: Path to Tomcat installation directory
        
        Returns:
            Dictionary with start status and details
        """
        try:
            # Validate Tomcat home exists
            if not os.path.exists(tomcat_home):
                return {
                    "name": self.name,
                    "status": "Failed",
                    "command": "start_tomcat",
                    "output": f"Tomcat directory not found: {tomcat_home}",
                    "details": f"Invalid TOMCAT_HOME: {tomcat_home}"
                }
            
            # Get startup script path
            bin_dir = os.path.join(tomcat_home, 'bin')
            if os.name == 'nt':  # Windows
                startup_script = os.path.join(bin_dir, 'startup.bat')
            else:  # Unix-like
                startup_script = os.path.join(bin_dir, 'startup.sh')
            
            if not os.path.exists(startup_script):
                return {
                    "name": self.name,
                    "status": "Failed",
                    "command": "start_tomcat",
                    "output": f"Startup script not found: {startup_script}",
                    "details": "Invalid Tomcat installation - missing startup script"
                }
            
            # Start Tomcat
            print(f"Starting Tomcat from: {tomcat_home}")
            
            if os.name == 'nt':  # Windows
                # Start in new console window
                process = subprocess.Popen(
                    [startup_script],
                    cwd=bin_dir,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            else:  # Unix-like
                process = subprocess.Popen(
                    [startup_script],
                    cwd=bin_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            
            # Wait a moment for startup to initiate
            time.sleep(2)
            
            output_msg = f"""
                Tomcat startup initiated!

                TOMCAT_HOME: {tomcat_home}
                Startup Script: {startup_script}

                Tomcat is starting on port 8080.
                Access at: http://localhost:8080

                Please wait 10-15 seconds for Tomcat to fully start.
                Check logs at: {os.path.join(tomcat_home, 'logs')}
                            """.strip()
            
            return {
                "name": self.name,
                "status": "Success",
                "command": f"Start Tomcat at {tomcat_home}",
                "output": output_msg,
                "details": "Tomcat startup initiated successfully"
            }
            
        except Exception as e:
            return {
                "name": self.name,
                "status": "Failed",
                "command": "start_tomcat",
                "output": str(e),
                "details": f"Failed to start Tomcat: {str(e)}"
            }


if __name__ == "__main__":
    # Test
    starter = StartTomcat()
    result = starter.run(tomcat_home="C:\\temp\\tomcat_test\\apache-tomcat-10.1.34")
    
    print(f"Status: {result['status']}")
    print(f"Details: {result['details']}")
    print(f"\n{result['output']}")
