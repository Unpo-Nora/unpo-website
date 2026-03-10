import os
import re

frontend_dir = r"c:\Users\user\.gemini\antigravity\scratch\UNPO_NORA_System\frontend"

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    
    # Replace simple string localhost:8000
    # e.g. 'http://localhost:8000/auth/me' -> `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/auth/me`
    content = re.sub(r"'http://localhost:8000(/.*?)'", r"`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}\1`", content)
    content = re.sub(r'"http://localhost:8000(/.*?)"', r"`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}\1`", content)
    
    # Replace dynamic string `http://${host}:8000/` or `http://localhost:8000/`
    content = re.sub(r"`http://\${[^}]+}:8000(/.*?)`", r"`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}\1`", content)
    content = re.sub(r"`http://localhost:8000(/.*?)`", r"`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}\1`", content)
    
    # Fix the host variable if it's unused now (optional but good)
    # Actually just leave it, it might cause unused warning but won't break.
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

for root, _, files in os.walk(frontend_dir):
    if "node_modules" in root or ".next" in root:
        continue
    for file in files:
        if file.endswith(('.ts', '.tsx', '.js', '.jsx')):
            process_file(os.path.join(root, file))

print("Done.")
