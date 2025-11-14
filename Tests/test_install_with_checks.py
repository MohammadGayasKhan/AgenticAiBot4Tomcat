import sys
import os

# Add the Tools directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Tools'))

from Installation.tomcat_install import InstallTomcat

print("Testing Tomcat Installation with Prerequisite Checks...\n")

installer = InstallTomcat()
result = installer.run(
    install_path="C:\\temp\\tomcat_test",
    version="10.1.34"
)

print("\n" + "="*60)
print("Installation Result:")
print("="*60)
print(f"Status: {result['status']}")
print(f"Details: {result['details']}")
print(f"\n{result['output']}")
