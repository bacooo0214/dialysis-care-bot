import subprocess
import re
import sys

cmd = ["ssh", "-p", "443", "-o", "StrictHostKeyChecking=no", "-R0:127.0.0.1:8000", "a.pinggy.io", "b"]
print("Starting ssh...", flush=True)
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

for line in proc.stdout:
    print("STDOUT:", line.strip(), flush=True)
    if "pinggy.link" in line:
        print("FOUND URL:", line.strip(), flush=True)
        break

for line in proc.stderr:
    print("STDERR:", line.strip(), flush=True)
