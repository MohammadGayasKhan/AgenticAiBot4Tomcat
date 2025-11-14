import subprocess
import time

def run_command(step_num, total_steps, description, command):
    print(f"\n[{step_num}/{total_steps}] {description}")
    print("-"*70)
    result = subprocess.run(
        ['python', 'main_langchain.py'],
        input=f'{command}\n',
        capture_output=True,
        text=True,
        cwd=r'C:\Users\mohammadgayk\Projects\general_assistance_bot'
    )
    print(result.stdout)
    return result

print("="*70)
print("COMPREHENSIVE TOMCAT LIFECYCLE TEST")
print("="*70)

# Step 1: Uninstall (in case it's already installed)
run_command(1, 10, "Uninstall Tomcat (if exists)", "uninstall tomcat")
time.sleep(2)

# Step 2: Install Tomcat
run_command(2, 10, "Install Tomcat", "install tomcat")
time.sleep(2)

# Step 3: Start Tomcat
run_command(3, 10, "Start Tomcat", "start tomcat")
print("\n[Waiting 15 seconds for Tomcat to fully start...]")
time.sleep(15)

# Step 4: Check port (should be IN USE)
run_command(4, 10, "Check if port 8080 is in use (should be BUSY)", "check if port 8080 is free")
time.sleep(2)

# Step 5: Stop Tomcat
run_command(5, 10, "Stop Tomcat", "stop tomcat")
print("\n[Waiting 5 seconds for Tomcat to fully stop...]")
time.sleep(5)

# Step 6: Uninstall Tomcat
run_command(6, 10, "Uninstall Tomcat", "uninstall tomcat")
time.sleep(2)

# Step 7: Try to start (should fail - not installed)
run_command(7, 10, "Try to start Tomcat (should FAIL - not installed)", "start tomcat")
time.sleep(2)

# Step 8: Install again
run_command(8, 10, "Install Tomcat again", "install tomcat")
time.sleep(2)

# Step 9: Start Tomcat
run_command(9, 10, "Start Tomcat", "start tomcat")
print("\n[Waiting 15 seconds for Tomcat to fully start...]")
time.sleep(15)

# Step 10: Stop Tomcat
run_command(10, 10, "Stop Tomcat", "stop tomcat")

print("\n" + "="*70)
print("COMPREHENSIVE TEST SEQUENCE COMPLETE")
print("="*70)
