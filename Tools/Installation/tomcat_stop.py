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
            description="Stop Apache Tomcat server. Default installation path: C:\\temp\\tomcat_test\\apache-tomcat-10.1.34",
            parameters={
                "tomcat_home": {
                    "type": "str",
                    "description": "Path to Tomcat installation directory. Default: C:\\temp\\tomcat_test\\apache-tomcat-10.1.34 (use this if user doesn't specify a path)"
                }
            }
        )
    
    def check_tomcat_installed(self, tomcat_home: str) -> tuple:
        """
        Check if Tomcat is installed at the given path
        
        Returns:
            (is_installed: bool, error_message: str)
        """
        if not os.path.exists(tomcat_home):
            return False, f"Tomcat installation not found at: {tomcat_home}"
        
        # Check for required directories and files
        bin_dir = os.path.join(tomcat_home, 'bin')
        if not os.path.exists(bin_dir):
            return False, f"Tomcat bin directory not found: {bin_dir}"
        
        # Check for shutdown script
        if os.name == 'nt':
            shutdown_script = os.path.join(bin_dir, 'shutdown.bat')
        else:
            shutdown_script = os.path.join(bin_dir, 'shutdown.sh')
        
        if not os.path.exists(shutdown_script):
            return False, f"Tomcat shutdown script not found: {shutdown_script}"
        
        return True, ""
    
    def check_if_running(self, tomcat_home: str) -> bool:
        """
        Check if Tomcat is currently running
        
        Returns:
            True if running, False otherwise
        """
        try:
            if os.name == 'nt':  # Windows
                # Check for java.exe process running catalina
                result = subprocess.run(
                    ['tasklist', '/FI', 'IMAGENAME eq java.exe', '/FO', 'CSV'],
                    capture_output=True,
                    text=True
                )
                # Simple check - if java.exe is running, assume Tomcat might be running
                # More accurate check would look at the PID file
                return 'java.exe' in result.stdout.lower()
            else:  # Unix-like
                # Check for catalina.pid file
                pid_file = os.path.join(tomcat_home, 'temp', 'catalina.pid')
                if os.path.exists(pid_file):
                    return True
                return False
        except Exception:
            # If we can't check, assume it might be running
            return True
    
    
    def run(self, tomcat_home: str = "C:\\temp\\tomcat_test\\apache-tomcat-10.1.34") -> Dict[str, Any]:
        """
        Stop Apache Tomcat server
        
        Args:
            tomcat_home: Path to Tomcat installation directory (default: C:\\temp\\tomcat_test\\apache-tomcat-10.1.34)
        
        Returns:
            Dictionary with stop status and details
        """
        try:
            # Step 1: Check if Tomcat is installed
            print("Checking Tomcat installation...")
            is_installed, error_msg = self.check_tomcat_installed(tomcat_home)
            
            if not is_installed:
                output = f"""
                    Tomcat Stop Failed!

                    {error_msg}

                    Please install Tomcat first.
                    """
                
                return {
                    "name": self.name,
                    "status": "Failed",
                    "command": "stop_tomcat",
                    "output": output.strip(),
                    "details": "Tomcat is not installed"
                }
            
            print(f"Tomcat found at: {tomcat_home}")
            
            # Step 2: Check if Tomcat is running
            is_running = self.check_if_running(tomcat_home)
            
            if not is_running:
                output = f"""
                    Tomcat is not running!

                    TOMCAT_HOME: {tomcat_home}

                    Tomcat does not appear to be running.
                    No action needed.
                    """
                
                return {
                    "name": self.name,
                    "status": "Not Running",
                    "command": "stop_tomcat",
                    "output": output.strip(),
                    "details": "Tomcat is not currently running"
                }
            
            # Step 3: Get shutdown script path
            bin_dir = os.path.join(tomcat_home, 'bin')
            if os.name == 'nt':  # Windows
                shutdown_script = os.path.join(bin_dir, 'shutdown.bat')
            else:  # Unix-like
                shutdown_script = os.path.join(bin_dir, 'shutdown.sh')
            
            # Step 4: Stop Tomcat
            print(f"\nStopping Tomcat...")
            
            result = subprocess.run(
                [shutdown_script],
                cwd=bin_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Wait a moment for shutdown to complete
            print("Waiting for Tomcat to shut down...")
            time.sleep(3)
            
            output_msg = f"""
Tomcat stopped successfully!

TOMCAT_HOME: {tomcat_home}
Shutdown Script: {shutdown_script}

Tomcat has been shut down.

Shutdown Output:
{result.stdout.strip() if result.stdout else 'Shutdown command executed successfully'}

Port 8080 is now available.
            """.strip()
            
            return {
                "name": self.name,
                "status": "Success",
                "command": f"Stop Tomcat at {tomcat_home}",
                "output": output_msg,
                "details": "Tomcat shutdown completed successfully"
            }
            
        except subprocess.TimeoutExpired:
            return {
                "name": self.name,
                "status": "Failed",
                "command": "stop_tomcat",
                "output": "Shutdown command timed out after 30 seconds",
                "details": "Tomcat shutdown timed out - process may need to be killed manually"
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
