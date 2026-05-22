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
    print(f"🔄 Bumping get_fit_together.py to version {new_version}...")
    with open('get_fit_together.py', 'r', encoding='utf-8') as file:
        lines = file.readlines()

    with open('get_fit_together.py', 'w', encoding='utf-8') as file:
        for line in lines:
            if line.startswith('APP_VERSION ='):
                file.write(f'APP_VERSION = "{new_version}"\n')
            else:
                file.write(line)
    print("✅ Version updated!")
else:
    print("⏭️ No version bump requested. Skipping straight to deployment...")

# 2. THE MULTI-BRANCH GIT DANCE
print("🚀 Packaging code on the DEV branch...")
subprocess.run(["git", "add", "."])
subprocess.run(["git", "commit", "-m", commit_msg])
subprocess.run(["git", "push", "origin", "dev"]) # Backs up your dev branch

print("🔀 Merging DEV into MAIN...")
subprocess.run(["git", "checkout", "main"])
subprocess.run(["git", "merge", "dev"])

print("☁️ Pushing MAIN to Production...")
subprocess.run(["git", "push", "origin", "main"]) # Triggers your live app update

print("🔙 Returning back to DEV branch...")
subprocess.run(["git", "checkout", "dev"])

print(f"🎉 Successfully deployed! Your workspace is ready for the next feature.")