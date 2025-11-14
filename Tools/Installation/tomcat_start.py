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
            description="Start Apache Tomcat server on port 8080. Default installation path: C:\\temp\\tomcat_test\\apache-tomcat-10.1.34",
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
        
        # Check for startup script
        if os.name == 'nt':
            startup_script = os.path.join(bin_dir, 'startup.bat')
        else:
            startup_script = os.path.join(bin_dir, 'startup.sh')
        
        if not os.path.exists(startup_script):
            return False, f"Tomcat startup script not found: {startup_script}"
        
        return True, ""
    
    def configure_environment_variables(self, tomcat_home: str) -> None:
        """
        Configure CATALINA_HOME and add Tomcat bin to PATH (Windows only)
        Similar to Java configuration pattern
        """
        try:
            if os.name == 'nt':  # Windows only
                print(f"Configuring environment variables...")
                
                tomcat_bin = os.path.join(tomcat_home, 'bin')
                
                # Set CATALINA_HOME using PowerShell
                ps_set_catalina = f'[Environment]::SetEnvironmentVariable("CATALINA_HOME", "{tomcat_home}", "User")'
                subprocess.run(['powershell', '-Command', ps_set_catalina], 
                             capture_output=True, text=True, check=True)
                
                # Get current PATH
                ps_get_path = '[Environment]::GetEnvironmentVariable("PATH", "User")'
                result = subprocess.run(['powershell', '-Command', ps_get_path],
                                      capture_output=True, text=True, check=True)
                old_path = result.stdout.strip()
                
                # Add Tomcat bin to PATH if not already there
                if tomcat_bin.lower() not in old_path.lower():
                    new_path = f"{tomcat_bin};{old_path}"
                    ps_set_path = f'[Environment]::SetEnvironmentVariable("PATH", "{new_path}", "User")'
                    subprocess.run(['powershell', '-Command', ps_set_path],
                                 capture_output=True, text=True, check=True)
                    print(f"Added {tomcat_bin} to PATH")
                else:
                    print(f"Tomcat bin already in PATH")
                
                # Update current session environment
                os.environ['CATALINA_HOME'] = tomcat_home
                os.environ['PATH'] = f"{tomcat_bin};{os.environ.get('PATH', '')}"
                
                print(f"Environment variables configured:")
                print(f"  CATALINA_HOME = {tomcat_home}")
                print(f"  PATH updated with {tomcat_bin}")
            else:
                # For Unix-like systems, just set for current session
                os.environ['CATALINA_HOME'] = tomcat_home
                print(f"CATALINA_HOME set to: {tomcat_home} (current session only)")
                
        except Exception as e:
            print(f"Warning: Could not configure environment variables: {e}")
            # Continue anyway - not critical for startup
    
    
    def run(self, tomcat_home: str = "C:\\temp\\tomcat_test\\apache-tomcat-10.1.34") -> Dict[str, Any]:
        """
        Start Apache Tomcat server on port 8080
        
        Args:
            tomcat_home: Path to Tomcat installation directory (default: C:\\temp\\tomcat_test\\apache-tomcat-10.1.34)
        
        Returns:
            Dictionary with start status and details
        """
        try:
            # Step 1: Check if Tomcat is installed
            print("Checking Tomcat installation...")
            is_installed, error_msg = self.check_tomcat_installed(tomcat_home)
            
            if not is_installed:
                output = f"""
                    Tomcat Start Failed!

                    {error_msg}

                    Please install Tomcat first before attempting to start it.
                    """
                
                return {
                    "name": self.name,
                    "status": "Failed",
                    "command": "start_tomcat",
                    "output": output.strip(),
                    "details": "Tomcat is not installed"
                }
            
            print(f"Tomcat found at: {tomcat_home}")
            
            # Step 2: Configure environment variables
            self.configure_environment_variables(tomcat_home)
            
            # Step 3: Get startup script path
            bin_dir = os.path.join(tomcat_home, 'bin')
            if os.name == 'nt':  # Windows
                startup_script = os.path.join(bin_dir, 'startup.bat')
            else:  # Unix-like
                startup_script = os.path.join(bin_dir, 'startup.sh')
            
            # Step 4: Start Tomcat
            print(f"\nStarting Tomcat on port 8080...")
            
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
Tomcat started successfully!

CATALINA_HOME: {tomcat_home}
Startup Script: {startup_script}

Tomcat is starting on port 8080.
Access at: http://localhost:8080

Environment variables configured:
  - CATALINA_HOME set to Tomcat installation directory
  - PATH updated to include Tomcat bin directory

Please wait 10-15 seconds for Tomcat to fully start.
Check logs at: {os.path.join(tomcat_home, 'logs')}

Note: Restart your terminal to use the updated environment variables.
            """.strip()
            
            return {
                "name": self.name,
                "status": "Success",
                "command": f"Start Tomcat at {tomcat_home}",
                "output": output_msg,
                "details": "Tomcat startup initiated successfully on port 8080"
            }
            
        except Exception as e:
            return {
                "name": self.name,
                "status": "Failed",
                "command": "start_tomcat",
                "output": str(e),
                "details": f"Failed to start Tomcat: {str(e)}"
            }


# if __name__ == "__main__":
#     # Test
#     starter = StartTomcat()
#     result = starter.run(tomcat_home="C:\\temp\\tomcat_test\\apache-tomcat-10.1.34")
    
#     print(f"Status: {result['status']}")
#     print(f"Details: {result['details']}")
#     print(f"\n{result['output']}")
