import os

frontend_dir = r"c:\Users\user\.gemini\antigravity\scratch\UNPO_NORA_System\frontend\components"

replacements = [
    ('`http://${host}:8000`;', '`${process.env.NEXT_PUBLIC_API_URL || \'http://localhost:8000\'}`;'),
    ('`http://${currentHost}:8000`;', '`${process.env.NEXT_PUBLIC_API_URL || \'http://localhost:8000\'}`;'),
    ('`http://localhost:8000${imgUrl}`', '`${process.env.NEXT_PUBLIC_API_URL || \'http://localhost:8000\'}${imgUrl}`'),
    ('`http://localhost:8000${c.product_image}`', '`${process.env.NEXT_PUBLIC_API_URL || \'http://localhost:8000\'}${c.product_image}`')
]

for root, _, files in os.walk(frontend_dir):
    for file in files:
        if file.endswith(('.tsx', '.ts')):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            original = content
            
            for old, new in replacements:
                content = content.replace(old, new)
                
            if content != original:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Fixed {filepath}")
print("Done.")
