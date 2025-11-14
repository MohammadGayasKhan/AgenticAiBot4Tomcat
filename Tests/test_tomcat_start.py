import sys
import os

# Add the Tools directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Tools'))

from Installation.tomcat_start import StartTomcat

print("Testing Tomcat Start with Environment Configuration...\n")

starter = StartTomcat()
result = starter.run(
    tomcat_home="C:\\temp\\tomcat_test\\apache-tomcat-10.1.34"
)

print("\n" + "="*60)
print("Start Result:")
print("="*60)
print(f"Status: {result['status']}")
print(f"Details: {result['details']}")
print(f"\n{result['output']}")
