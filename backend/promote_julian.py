from app.database import SessionLocal
from app import models

def promote_julian():
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == "julianv@unpo.com.ar").first()
        if user:
            user.role = "admin"
            db.commit()
            print(f"Usuario {user.email} promovido a ADMIN exitosamente.")
        else:
            # Si no existe, lo creamos (asumiendo password por defecto para que el usuario la cambie)
            from app.utils import auth
            new_user = models.User(
                email="julianv@unpo.com.ar",
                hashed_password=auth.get_password_hash("Julian*2024"), # Password provisoria
                full_name="Julian V",
                role="admin"
            )
            db.add(new_user)
            db.commit()
            print(f"Usuario {new_user.email} creado como ADMIN exitosamente.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    promote_julian()
