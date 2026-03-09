from sqlalchemy import text
from app.database import engine

def migrate():
    with engine.connect() as conn:
        print("Verificando columnas de la tabla 'leads'...")
        
        # Añadir status si falta (como VARCHAR primero para seguridad)
        try:
            conn.execute(text("ALTER TABLE leads ADD COLUMN status VARCHAR DEFAULT 'NEW';"))
            print("Columna 'status' añadida.")
        except Exception as e:
            print(f"Columna 'status' ya existe o error: {e}")

        # Añadir contacted_at
        try:
            conn.execute(text("ALTER TABLE leads ADD COLUMN contacted_at TIMESTAMP WITH TIME ZONE;"))
            print("Columna 'contacted_at' añadida.")
        except Exception as e:
            print(f"Columna 'contacted_at' ya existe o error: {e}")

        # Asegurar feedback_status
        try:
            conn.execute(text("ALTER TABLE leads ADD COLUMN feedback_status VARCHAR;"))
            print("Columna 'feedback_status' añadida.")
        except Exception as e:
            print(f"Columna 'feedback_status' ya existe o error: {e}")

        # Asegurar notes
        try:
            conn.execute(text("ALTER TABLE leads ADD COLUMN notes TEXT;"))
            print("Columna 'notes' añadida.")
        except Exception as e:
            print(f"Columna 'notes' ya existe o error: {e}")

        conn.commit()
        print("Migración finalizada.")

if __name__ == "__main__":
    migrate()
