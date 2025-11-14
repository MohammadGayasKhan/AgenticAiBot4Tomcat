"""
Direct test script to start Tomcat and check port 8080
Bypasses LLM and calls tools directly
"""

import sys
import os
import time

# Add Tools directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'Tools'))

from Installation.tomcat_start import StartTomcat
from pre_requisit_check.check_ports import CheckPorts


def main():
    print("="*70)
    print("DIRECT TOOL TEST: Start Tomcat and Check Port 8080")
    print("="*70)
    print()
    
    # Step 1: Start Tomcat
    print("[1/3] Starting Tomcat...")
    print("-"*70)
    starter = StartTomcat()
    start_result = starter.run()  # Uses default path
    
    print(f"Status: {start_result['status']}")
    print(f"Details: {start_result['details']}")
    if start_result['output']:
        print(start_result['output'])
    print()
    
    if start_result['status'] != "Success":
        print("❌ Failed to start Tomcat. Exiting.")
        return
    
    # Step 2: Wait for Tomcat to start
    print("[2/3] Waiting 15 seconds for Tomcat to fully start...")
    print("-"*70)
    time.sleep(15)
    print("✓ Wait complete")
    print()
    
    # Step 3: Check port 8080
    print("[3/3] Checking if port 8080 is in use...")
    print("-"*70)
    port_checker = CheckPorts()
    port_result = port_checker.run(ports=[8080])
    
    print(f"Status: {port_result['status']}")
    print(f"Details: {port_result['details']}")
    if port_result['output']:
        print(port_result['output'])
    print()
    
    # Interpret result
    print("="*70)
    print("RESULT:")
    print("="*70)
    
    if port_result['status'] == "Failed":
        print("✓ Port 8080 is IN USE - Tomcat is running successfully!")
        print()
        print("To access Tomcat, open: http://localhost:8080")
    else:
        print("⚠ Port 8080 is FREE - Tomcat may not have started properly")
        print()
        print("Check logs at: C:\\temp\\tomcat_test\\apache-tomcat-10.1.34\\logs")
    
    print("="*70)


if __name__ == "__main__":
    main()
