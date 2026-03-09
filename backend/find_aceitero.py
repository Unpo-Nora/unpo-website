from app.database import SessionLocal
from app.models import Product

db = SessionLocal()

print("--- ALL PRODUCTS WITH ACEIT OR DISPENS ---")
for p in db.query(Product).all():
    name = p.name.lower()
    if 'aceit' in name or 'disp' in name:
        print(f"{p.sku} - {p.name}")

db.close()
