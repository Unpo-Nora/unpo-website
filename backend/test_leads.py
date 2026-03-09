from app.database import SessionLocal
from app import crud, models

def test():
    db = SessionLocal()
    print("--- Test: Fetching all leads ---")
    all_leads = crud.get_leads(db, limit=5)
    print(f"Total leads fetch (no filter): {len(all_leads)}")
    for l in all_leads:
        print(f"ID: {l.id}, Status: {l.status}, Type: {type(l.status)}")

    print("\n--- Test: Fetching NEW leads ---")
    new_leads = crud.get_leads(db, status="NEW", limit=5)
    print(f"Total NEW leads fetch: {len(new_leads)}")
    for l in new_leads:
        print(f"ID: {l.id}, Status: {l.status}")

    print("\n--- Test: Fetching CONTACTED leads ---")
    contacted_leads = crud.get_leads(db, status="CONTACTED", limit=5)
    print(f"Total CONTACTED leads fetch: {len(contacted_leads)}")

if __name__ == "__main__":
    test()
