from app.database import SessionLocal
from app import crud, models

def debug_router_logic():
    db = SessionLocal()
    # Simulate Julian
    user = db.query(models.User).filter(models.User.email == "julianv@unpo.com.ar").first()
    if not user:
        print("User Julian not found")
        return
    
    print(f"User: {user.email}, Role: {user.role}")
    
    # Logic in router:
    if user.role == "admin":
        print("Executing admin logic: get_leads(db, skip=0, limit=1000, status=None)")
        leads = crud.get_leads(db, skip=0, limit=1000, status=None)
        print(f"Leads returned: {len(leads)}")
        if leads:
            print(f"First lead ID: {leads[0].id}, Status: {leads[0].status}")
    else:
        print("Executing seller logic")

if __name__ == "__main__":
    debug_router_logic()
