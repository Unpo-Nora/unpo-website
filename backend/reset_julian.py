from app.database import SessionLocal
from app import models
from app.utils import auth

def reset_julian_password():
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == "julianv@unpo.com.ar").first()
        if user:
            user.hashed_password = auth.get_password_hash("Julian*2024")
            user.role = "admin"
            user.is_active = True
            db.commit()
            print(f"Password reset for {user.email}. New password is 'Julian*2024'")
        else:
            print("User not found.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_julian_password()
