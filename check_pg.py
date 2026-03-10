import sys
sys.path.append('backend')
from sqlalchemy import create_engine, text

# Conectando a localhost en lugar de 'db'
engine = create_engine('postgresql://unpo_admin:secure_password_123@localhost:5432/unpo_nora_db')

with engine.connect() as conn:
    # Get user
    try:
        result = conn.execute(text("SELECT id, email, is_active, is_superuser, role, hashed_password FROM users WHERE email = 'julianv@unpo.com.ar'"))
        rows = result.fetchall()
        print("User julianv@unpo.com.ar:")
        for row in rows:
            print(row)
    except Exception as e:
        print("Error:", e)
