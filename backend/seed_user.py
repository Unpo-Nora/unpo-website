from app.database import SessionLocal
from app import crud, models
import os

def seed_user():
    db = SessionLocal()
    users_to_create = [
        {
            "email": "admin@unpoboton.com",
            "password": "admin_password_123",
            "full_name": "Admin UNPO",
            "role": "admin"
        },
        {
            "email": "julianv@unpo.com.ar",
            "password": "Jvelazquez*18",
            "full_name": "Julian Velazquez",
            "role": "admin"
        }
    ]
    
    try:
        for u_data in users_to_create:
            existing = crud.get_user_by_email(db, u_data["email"])
            if not existing:
                print(f"Creando usuario: {u_data['email']}")
                crud.create_user(db, u_data)
            else:
                print(f"Actualizando usuario existente: {u_data['email']}")
                existing.full_name = u_data["full_name"]
                db.commit()
            print(f"Usuario {u_data['email']} procesado con éxito.")
    except Exception as e:
        print(f"Error al crear usuario: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_user()
