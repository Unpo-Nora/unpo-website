import shutil
import os

src = r"c:\Users\user\.gemini\antigravity\brain\cf450a45-7f93-4a6e-8fbb-395cb113c3a7\media__1771518844238.jpg"
dst = r"c:\Users\user\.gemini\antigravity\scratch\UNPO_NORA_System\frontend\public\nora\smart_table_white.jpg"

try:
    if not os.path.exists(src):
        print(f"Error: Source file not found: {src}")
    else:
        shutil.copy2(src, dst)
        print(f"Success: Copied to {dst}")
        if os.path.exists(dst):
             print(f"Verified: Destination file exists, size: {os.path.getsize(dst)}")
        else:
             print("Error: Destination file missing after copy")

except Exception as e:
    print(f"Exception: {e}")
