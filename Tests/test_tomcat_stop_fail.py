import sys
import os

# Add the Tools directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Tools'))

from Installation.tomcat_stop import StopTomcat

print("Testing Tomcat Stop with non-existent installation...\n")

stopper = StopTomcat()
result = stopper.run(
    tomcat_home="C:\\nonexistent\\tomcat"
)

print("\n" + "="*60)
print("Stop Result:")
print("="*60)
print(f"Status: {result['status']}")
print(f"Details: {result['details']}")
print(f"\n{result['output']}")
