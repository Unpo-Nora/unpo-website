from app.database import SessionLocal
from app.models import Product

db = SessionLocal()

for sku in ['10300028', '20800061']:
    p = db.query(Product).filter(Product.sku == sku).first()
    if p:
        print(f"SKU: {p.sku}")
        print(f"NAME: {p.name}")
        print(f"CATEGORY: {p.category.name if p.category else 'None'}")
        print(f"DESC: {p.description}")
        print("-" * 20)

db.close()
