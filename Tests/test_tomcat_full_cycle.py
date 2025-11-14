import subprocess
import time

print("="*70)
print("COMPLETE TOMCAT TEST SEQUENCE")
print("="*70)

# Test 1: Start Tomcat
print("\n[1/4] Starting Tomcat...")
print("-"*70)
result = subprocess.run(
    ['python', 'main_langchain.py'],
    input='start tomcat\n',
    capture_output=True,
    text=True,
    cwd=r'C:\Users\mohammadgayk\Projects\general_assistance_bot'
)
print(result.stdout)

# Wait for Tomcat to fully start
print("\n[Waiting 15 seconds for Tomcat to fully start...]")
time.sleep(15)

# Test 2: Check if port 8080 is running
print("\n[2/4] Checking if port 8080 is in use...")
print("-"*70)
result = subprocess.run(
    ['python', 'main_langchain.py'],
    input='check if port 8080 is free\n',
    capture_output=True,
    text=True,
    cwd=r'C:\Users\mohammadgayk\Projects\general_assistance_bot'
)
print(result.stdout)

# Test 3: Stop Tomcat
print("\n[3/4] Stopping Tomcat...")
print("-"*70)
result = subprocess.run(
    ['python', 'main_langchain.py'],
    input='stop tomcat\n',
    capture_output=True,
    text=True,
    cwd=r'C:\Users\mohammadgayk\Projects\general_assistance_bot'
)
print(result.stdout)

# Wait for Tomcat to fully stop
print("\n[Waiting 5 seconds for Tomcat to fully stop...]")
time.sleep(5)

# Test 4: Check if port 8080 is free again
print("\n[4/4] Checking if port 8080 is free after stopping...")
print("-"*70)
result = subprocess.run(
    ['python', 'main_langchain.py'],
    input='check if port 8080 is free\n',
    capture_output=True,
    text=True,
    cwd=r'C:\Users\mohammadgayk\Projects\general_assistance_bot'
)
print(result.stdout)

print("\n" + "="*70)
print("TEST SEQUENCE COMPLETE")
print("="*70)
