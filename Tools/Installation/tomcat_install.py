import os
import zipfile
import urllib.request
import subprocess
import sys
from typing import Dict, Any
from .tool_base import Tool

# Import prerequisite check tools
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from pre_requisit_check.check_disk import CheckDisk
from pre_requisit_check.check_java import CheckJava
from pre_requisit_check.check_ports import CheckPorts
from pre_requisit_check.check_ram import CheckRAM


class InstallTomcat(Tool):
    """Download and install Apache Tomcat 10.x.x"""
    
    def __init__(self):
        super().__init__(
            name="install_tomcat",
            description="Download and install Apache Tomcat 10.x.x",
            parameters={
                "install_path": {
                    "type": "str",
                    "description": "Directory path where Tomcat should be installed (default: C:\\apache-tomcat)"
                },
                "version": {
                    "type": "str", 
                    "description": "Tomcat version to install (default: 10.1.34)"
                }
            }
        )
    
    def download_tomcat(self, version: str = "10.1.34", download_path: str = "C:\\temp\\tomcat_test") -> str:
        """Download Tomcat zip file"""
        # Construct download URL - use archive.apache.org for reliable access
        major_version = version.split('.')[0]
        download_url = f"https://archive.apache.org/dist/tomcat/tomcat-{major_version}/v{version}/bin/apache-tomcat-{version}.zip"
        
        zip_file = os.path.join(download_path, f"apache-tomcat-{version}.zip")
        
        print(f"Downloading Tomcat {version} from {download_url}...")
        
        try:
            # Download with progress
            urllib.request.urlretrieve(download_url, zip_file)
            print(f"Downloaded to: {zip_file}")
            return zip_file
        except Exception as e:
            raise Exception(f"Failed to download Tomcat: {e}")
    
    def extract_tomcat(self, zip_file: str, install_path: str) -> str:
        """Extract Tomcat zip file"""
        print(f"Extracting {zip_file} to {install_path}...")
        
        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(install_path)
            
            # Get the extracted folder name (apache-tomcat-version)
            extracted_folder = os.path.join(
                install_path, 
                os.path.basename(zip_file).replace('.zip', '')
            )
            
            print(f"Extracted to: {extracted_folder}")
            return extracted_folder
            
        except Exception as e:
            raise Exception(f"Failed to extract Tomcat: {e}")
    
    def configure_tomcat(self, tomcat_dir: str) -> None:
        """Basic Tomcat configuration and set environment variables"""
        try:
            # Make shell scripts executable (for Linux/Mac)
            bin_dir = os.path.join(tomcat_dir, 'bin')
            if os.name != 'nt':  # Unix-like systems
                for script in os.listdir(bin_dir):
                    if script.endswith('.sh'):
                        script_path = os.path.join(bin_dir, script)
                        os.chmod(script_path, 0o755)
            
            # Set CATALINA_HOME environment variable
            self.set_catalina_home(tomcat_dir)
            
            print("Tomcat configured successfully")
            
        except Exception as e:
            print(f"Warning: Configuration step had issues: {e}")
    
    def set_catalina_home(self, tomcat_dir: str) -> None:
        """Set CATALINA_HOME environment variable permanently (Windows)"""
        try:
            if os.name == 'nt':  # Windows
                # Set user environment variable permanently
                subprocess.run(
                    ['setx', 'CATALINA_HOME', tomcat_dir],
                    check=True,
                    capture_output=True,
                    text=True
                )
                # Also set for current session
                os.environ['CATALINA_HOME'] = tomcat_dir
                print(f"Environment variable CATALINA_HOME set to: {tomcat_dir}")
            else:  # Unix-like systems
                # Set for current session
                os.environ['CATALINA_HOME'] = tomcat_dir
                print(f"CATALINA_HOME set to: {tomcat_dir}")
                print("Note: Add 'export CATALINA_HOME={tomcat_dir}' to ~/.bashrc or ~/.zshrc for persistence")
                
        except Exception as e:
            print(f"Warning: Could not set CATALINA_HOME environment variable: {e}")
    
    def run_prerequisite_checks(self, install_path: str) -> tuple:
        """
        Run all prerequisite checks before installation
        
        Returns:
            (all_passed: bool, failed_checks: list, check_results: dict)
        """
        print("\n" + "="*60)
        print("Running Prerequisite Checks...")
        print("="*60 + "\n")
        
        failed_checks = []
        check_results = {}
        
        # 1. Check Disk Space (need at least 250 MB for Tomcat)
        print("1. Checking disk space...")
        disk_checker = CheckDisk()
        # Get the drive path from install_path
        drive_path = os.path.splitdrive(install_path)[0] + "\\" if os.path.splitdrive(install_path)[0] else install_path
        disk_result = disk_checker.run(min_free_mb=250, path=drive_path)
        check_results['disk'] = disk_result
        
        # Check disk result (uses "space available" instead of "status")
        disk_status = disk_result.get('space available', 'No')
        print(f"   Space Available: {disk_status}")
        print(f"   Details: {disk_result['details']}\n")
        
        if disk_status != "Yes":
            failed_checks.append(f"Disk Space: {disk_result['details']}")
        
        # 2. Check Java Installation
        print("2. Checking Java installation...")
        java_checker = CheckJava()
        java_result = java_checker.run()
        check_results['java'] = java_result
        print(f"   Status: {java_result['status']}")
        print(f"   Details: {java_result['details']}\n")
        
        if java_result['status'] != "Success":
            failed_checks.append(f"Java: {java_result['details']}")
        
        # 3. Check Required Ports (8080, 8005, 8009)
        print("3. Checking required ports (8080, 8005, 8009)...")
        port_checker = CheckPorts()
        port_result = port_checker.run(ports=[8080, 8005, 8009])
        check_results['ports'] = port_result
        print(f"   Status: {port_result['status']}")
        print(f"   Details: {port_result['details']}\n")
        
        if port_result['status'] != "Success":
            failed_checks.append(f"Ports: {port_result['details']}")
        
        # 4. Check RAM (need at least 512 MB)
        print("4. Checking RAM availability...")
        ram_checker = CheckRAM()
        ram_result = ram_checker.run()
        check_results['ram'] = ram_result
        print(f"   Status: {ram_result['status']}")
        print(f"   Details: {ram_result['details']}\n")
        
        if ram_result['status'] != "Success":
            failed_checks.append(f"RAM: {ram_result['details']}")
        
        print("="*60)
        if failed_checks:
            print("❌ Some prerequisite checks FAILED!")
            for check in failed_checks:
                print(f"   - {check}")
        else:
            print("✅ All prerequisite checks PASSED!")
        print("="*60 + "\n")
        
        return len(failed_checks) == 0, failed_checks, check_results
    
    def check_existing_installation(self, install_path: str, version: str) -> tuple:
        """
        Check if Tomcat is already installed
        
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
    
    def run(self, install_path: str = "C:\\apache-tomcat", version: str = "10.1.34") -> Dict[str, Any]:
        """
        Download and install Apache Tomcat
        
        Args:
            install_path: Directory where Tomcat should be installed
            version: Tomcat version to install (e.g., "10.1.34")
        
        Returns:
            Dictionary with installation status and details
        """
        try:
            # Check if already installed
            is_installed, existing_dir = self.check_existing_installation(install_path, version)
            
            if is_installed:
                startup_script = os.path.join(existing_dir, 'bin', 'startup.bat' if os.name == 'nt' else 'startup.sh')
                
                output = f"""
                    Tomcat {version} already exists!

                    Installation Directory: {existing_dir}
                    Startup Script: {startup_script}

                    Tomcat is already installed at this location.
                    To reinstall, please delete the existing directory first.
                    """
                
                return {
                    "status": "Already Exists",
                    "command": f"Check Tomcat {version}",
                    "output": output.strip(),
                    "details": f"Tomcat {version} already installed at {existing_dir}",
                    "tomcat_home": existing_dir
                }
            
            # Run prerequisite checks
            all_passed, failed_checks, check_results = self.run_prerequisite_checks(install_path)
            
            if not all_passed:
                failure_details = "\n".join([f"   - {check}" for check in failed_checks])
                output = f"""
                    Prerequisite checks FAILED!

                    The following checks did not pass:
                    {failure_details}

                    Please resolve these issues before installing Tomcat.
                    """
                
                return {
                    "status": "Failed",
                    "command": f"Install Tomcat {version} - Prerequisite Checks",
                    "output": output.strip(),
                    "details": f"Failed prerequisite checks: {', '.join(failed_checks)}",
                    "prerequisite_results": check_results
                }
            
            # Create install directory if it doesn't exist
            os.makedirs(install_path, exist_ok=True)
            
            # Step 1: Download Tomcat
            zip_file = self.download_tomcat(version, install_path)
            
            # Step 2: Extract Tomcat
            tomcat_dir = self.extract_tomcat(zip_file, install_path)
            
            # Step 3: Configure Tomcat
            self.configure_tomcat(tomcat_dir)
            
            # Step 4: Clean up zip file
            os.remove(zip_file)
            print(f"Cleaned up: {zip_file}")
            
            # Prepare output
            startup_script = os.path.join(tomcat_dir, 'bin', 'startup.bat' if os.name == 'nt' else 'startup.sh')
            shutdown_script = os.path.join(tomcat_dir, 'bin', 'shutdown.bat' if os.name == 'nt' else 'shutdown.sh')
            
            output = f"""
                    Tomcat {version} installed successfully!

                    Installation Directory: {tomcat_dir}
                    Environment Variable: CATALINA_HOME={tomcat_dir}
                    Startup Script: {startup_script}
                    Shutdown Script: {shutdown_script}

                    To start Tomcat:
                    {startup_script}

                    To stop Tomcat:
                    {shutdown_script}

                    Access Tomcat at: http://localhost:8080
                    
                    Note: CATALINA_HOME has been set. Restart your terminal for the variable to take effect.
                    """
            
            return {
                "status": "Success",
                "command": f"Install Tomcat {version}",
                "output": output.strip(),
                "details": f"Tomcat {version} installed to {tomcat_dir}",
                "tomcat_home": tomcat_dir
            }
            
        except Exception as e:
            return {
                "status": "Failed",
                "command": f"Install Tomcat {version}",
                "output": "",
                "details": f"Installation failed: {str(e)}"
            }


# if __name__ == "__main__":
#     # Test the installation
#     print("Starting Apache Tomcat Installation...\n")
    
#     installer = InstallTomcat()
#     result = installer.run(
#         install_path="C:\\temp\\tomcat_test",
#         version="10.1.34"
#     )
    
#     print("\n" + "="*60)
#     print("Installation Result:")
#     print("="*60)
#     print(f"Status: {result['status']}")
#     print(f"Details: {result['details']}")
#     if result['status'] in ['Success', 'Already Exists']:
#         print(f"\n{result['output']}")
