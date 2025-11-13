import os
import zipfile
import urllib.request
from typing import Dict, Any
from .tool_base import Tool


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
        """Basic Tomcat configuration"""
        try:
            # Make shell scripts executable (for Linux/Mac)
            bin_dir = os.path.join(tomcat_dir, 'bin')
            if os.name != 'nt':  # Unix-like systems
                for script in os.listdir(bin_dir):
                    if script.endswith('.sh'):
                        script_path = os.path.join(bin_dir, script)
                        os.chmod(script_path, 0o755)
            
            print("Tomcat configured successfully")
            
        except Exception as e:
            print(f"Warning: Configuration step had issues: {e}")
    
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
                    Startup Script: {startup_script}
                    Shutdown Script: {shutdown_script}

                    To start Tomcat:
                    {startup_script}

                    To stop Tomcat:
                    {shutdown_script}

                    Access Tomcat at: http://localhost:8080
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
