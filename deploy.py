import sys
import subprocess

# Check if the user provided a commit message
if len(sys.argv) < 2:
    print('⚠️ Usage: python deploy.py "<commit_message>"')
    sys.exit(1)

commit_msg = sys.argv[1]

print("🚀 Packaging code on the DEV branch...")
subprocess.run(["git", "add", "."])
subprocess.run(["git", "commit", "-m", commit_msg])
subprocess.run(["git", "push", "origin", "dev"]) 

print("🔀 Merging DEV into MAIN...")
subprocess.run(["git", "checkout", "main"])
subprocess.run(["git", "merge", "dev"])

print("☁️ Pushing MAIN to Production...")
subprocess.run(["git", "push", "origin", "main"]) 

print("🔙 Returning back to DEV branch...")
subprocess.run(["git", "checkout", "dev"])

print(f"🎉 Successfully deployed! Your workspace is ready for the next feature.")