import sys
from sqlalchemy import text
from app.database import engine
from app.models import Base

def upgrade():
    try:
        print("Creating new tables...")
        Base.metadata.create_all(bind=engine)
        print("Tables created.")
        
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE products ADD COLUMN price_breakdown JSON;"))
                conn.commit()
                print("Added price_breakdown to products.")
            except Exception as e:
                print("Error adding column (might already exist):", e)
        print("Upgrade complete.")
    except Exception as e:
        print("Total failure:", e)

if __name__ == "__main__":
    upgrade()
