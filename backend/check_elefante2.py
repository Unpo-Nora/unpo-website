from app.database import SessionLocal
from app.models import Product

db = SessionLocal()
p = db.query(Product).filter(Product.sku == '20800061').first()
print(f"SKU: {p.sku}, NAME: {p.name}, DESC: {p.description}")
db.close()
