import os
import shutil
from typing import Dict, Any
from .tool_base import Tool


class UninstallTomcat(Tool):
    """Uninstall Apache Tomcat"""
    
    def __init__(self):
        super().__init__(
            name="uninstall_tomcat",
            description="Uninstall Apache Tomcat 10.x.x",
            parameters={
                "install_path": {
                    "type": "str",
                    "description": "Directory path where Tomcat is installed (default: C:\\apache-tomcat)"
                },
                "version": {
                    "type": "str", 
                    "description": "Tomcat version to uninstall (default: 10.1.34)"
                }
            }
        )
    
    def check_installation(self, install_path: str = "C:\\apache-tomcat", version: str = "10.1.34") -> tuple:
        """
        Check if Tomcat is installed
        
        Returns:
            (is_installed: bool, tomcat_dir: str)
        """
        expected_dir = os.path.join(install_path, f"apache-tomcat-{version}")
        
        if os.path.exists(expected_dir):
            # Check if it looks like a valid Tomcat installation
            bin_dir = os.path.join(expected_dir, 'bin')
            startup_script = os.path.join(bin_dir, 'startup.bat' if os.name == 'nt' else 'startup.sh')
            
            if os.path.exists(bin_dir) and os.path.exists(startup_script):
                return True, expected_dir
        
        return False, None
    
    def is_tomcat_running(self, tomcat_dir: str) -> bool:
        """
        Check if Tomcat is currently running by looking for the catalina PID file
        
        Returns:
            True if running, False otherwise
        """
        pid_file = os.path.join(tomcat_dir, 'temp', 'catalina.pid')
        
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                # Check if process is actually running
                if os.name == 'nt':
                    # Windows: use tasklist
                    import subprocess
                    result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                          capture_output=True, text=True)
                    return str(pid) in result.stdout
                else:
                    # Unix: check if process exists
                    try:
                        os.kill(pid, 0)  # Signal 0 just checks if process exists
                        return True
                    except OSError:
                        return False
            except Exception:
                pass
        
        return False
    
    def uninstall_tomcat(self, tomcat_dir: str) -> None:
        """
        Remove Tomcat installation directory
        """
        print(f"Removing Tomcat directory: {tomcat_dir}...")
        
        try:
            shutil.rmtree(tomcat_dir)
            print(f"Successfully removed: {tomcat_dir}")
        except Exception as e:
            raise Exception(f"Failed to remove Tomcat directory: {e}")
    
    def run(self, install_path: str = "C:\\temp\\apache-tomcat", version: str = "10.1.34") -> Dict[str, Any]:
        """
        Uninstall Apache Tomcat
        
        Args:
            install_path: Directory where Tomcat is installed
            version: Tomcat version to uninstall (e.g., "10.1.34")
        
        Returns:
            Dictionary with uninstallation status and details
        """
        try:
            # Check if Tomcat is installed
            is_installed, tomcat_dir = self.check_installation(install_path, version)
            
            if not is_installed:
                output = f"""
                    Tomcat {version} is not installed!

                    Expected location: {os.path.join(install_path, f"apache-tomcat-{version}")}

                    No Tomcat installation found at this location.
                    """
                
                return {
                    "status": "Not Found",
                    "command": f"Uninstall Tomcat {version}",
                    "output": output.strip(),
                    "details": f"Tomcat {version} is not installed at {install_path}"
                }
            
            # Check if Tomcat is running
            if self.is_tomcat_running(tomcat_dir):
                shutdown_script = os.path.join(tomcat_dir, 'bin', 
                                              'shutdown.bat' if os.name == 'nt' else 'shutdown.sh')
                
                output = f"""
                    Cannot uninstall - Tomcat {version} is currently running!

                    Installation Directory: {tomcat_dir}

                    Please stop Tomcat before uninstalling:
                    {shutdown_script}

                    Or manually kill the Tomcat process and try again.
                    """
                
                return {
                    "status": "Failed",
                    "command": f"Uninstall Tomcat {version}",
                    "output": output.strip(),
                    "details": f"Tomcat {version} is running. Stop it before uninstalling."
                }
            
            # Perform uninstallation
            self.uninstall_tomcat(tomcat_dir)
            
            output = f"""
                    Tomcat {version} uninstalled successfully!

                    Removed directory: {tomcat_dir}

                    Tomcat has been completely removed from your system.
                    """
            
            return {
                "status": "Success",
                "command": f"Uninstall Tomcat {version}",
                "output": output.strip(),
                "details": f"Tomcat {version} successfully uninstalled from {tomcat_dir}"
            }
            
        except Exception as e:
            return {
                "status": "Failed",
                "command": f"Uninstall Tomcat {version}",
                "output": "",
                "details": f"Uninstallation failed: {str(e)}"
            }


# if __name__ == "__main__":
#     # Test the uninstallation
#     print("Starting Apache Tomcat Uninstallation...\n")
    
#     uninstaller = UninstallTomcat()
#     result = uninstaller.run(
#         install_path="C:\\temp\\tomcat_test",
#         version="10.1.34"
#     )
    
#     print("\n" + "="*60)
#     print("Uninstallation Result:")
#     print("="*60)
#     print(f"Status: {result['status']}")
#     print(f"Details: {result['details']}")
#     if result['status'] in ['Success', 'Not Found', 'Failed']:
#         print(f"\n{result['output']}")
