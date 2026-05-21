import sys
import subprocess

# Check if the user provided at least a commit message
if len(sys.argv) < 2:
    print('⚠️ Usage for minor update: python deploy.py "<commit_message>"')
    print('⚠️ Usage for version bump: python deploy.py <new_version> "<commit_message>"')
    sys.exit(1)

# Detect if the user passed 1 argument (message only) or 2 arguments (version + message)
if len(sys.argv) == 2:
    new_version = None
    commit_msg = sys.argv[1]
else:
    new_version = sys.argv[1]
    commit_msg = sys.argv[2]

# 1. BUMP VERSION (Only if a version number was provided)
if new_version:
    print(f"🔄 Bumping B52_Tracker_Final.py to version {new_version}...")
    with open('B52_Tracker_Final.py', 'r', encoding='utf-8') as file:
        lines = file.readlines()

    with open('B52_Tracker_Final.py', 'w', encoding='utf-8') as file:
        for line in lines:
            if line.startswith('APP_VERSION ='):
                file.write(f'APP_VERSION = "{new_version}"\n')
            else:
                file.write(line)
    print("✅ Version updated!")
else:
    print("⏭️ No version bump requested. Skipping straight to deployment...")

# 2. EXECUTE GIT COMMANDS
print("🚀 Packaging and pushing to GitHub...")
subprocess.run(["git", "add", "."])
subprocess.run(["git", "commit", "-m", commit_msg])
subprocess.run(["git", "push", "origin", "main"])

print("🎉 Successfully deployed to production!")