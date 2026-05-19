import sys
import os
import subprocess

# Check if the user provided the right arguments
if len(sys.argv) < 3:
    print('⚠️ Usage: python deploy.py <new_version> "<commit_message>"')
    print('Example: python deploy.py 1.0.2 "Fixed the Garmin bug"')
    sys.exit(1)

new_version = sys.argv[1]
commit_msg = sys.argv[2]

print(f"🔄 Bumping B52_Tracker_Final.py to version {new_version}...")

# 1. Read B52_Tracker_Final.py and find the version line
with open('B52_Tracker_Final.py', 'r', encoding='utf-8') as file:
    lines = file.readlines()

# 2. Overwrite B52_Tracker_Final.py with the new version
with open('B52_Tracker_Final.py', 'w', encoding='utf-8') as file:
    for line in lines:
        if line.startswith('APP_VERSION ='):
            file.write(f'APP_VERSION = "{new_version}"\n')
        else:
            file.write(line)

print("✅ Version updated! Pushing to GitHub...")

# 3. Execute the Git commands automatically
subprocess.run(["git", "add", "."])
subprocess.run(["git", "commit", "-m", commit_msg])
subprocess.run(["git", "push", "origin", "main"])

print(f"🚀 Version {new_version} successfully deployed to production!")