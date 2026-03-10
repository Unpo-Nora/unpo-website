from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    res = conn.execute(text("SELECT email FROM users")).fetchall()
    print("Usuarios:")
    for r in res:
        print(r[0])
