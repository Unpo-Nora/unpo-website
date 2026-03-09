from app.database import SessionLocal
from app import crud, models

def add_users():
    db = SessionLocal()
    users_to_create = [
        {
            "email": "gonzaloR@unpo.com.ar",
            "password": "Grobles*24",
            "full_name": "Gonzalo Robles",
            "role": "admin"
        },
        {
            "email": "pedroN@unpo.com.ar",
            "password": "Pnano*27",
            "full_name": "Pedro Nano",
            "role": "vendedor"
        }
    ]
    
    try:
        for u_data in users_to_create:
            existing = crud.get_user_by_email(db, u_data["email"])
            if not existing:
                print(f"Creando usuario: {u_data['email']} ({u_data['role']})")
                crud.create_user(db, u_data)
                print(f"Usuario {u_data['email']} creado con éxito.")
            else:
                print(f"El usuario {u_data['email']} ya existe.")
    except Exception as e:
        print(f"Error al crear usuarios: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    add_users()
