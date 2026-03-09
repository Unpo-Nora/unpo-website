from app.database import SessionLocal
from app.models import Product

db = SessionLocal()

# Find the product that is currently "Elefante de peluche" but is supposed to be "Aceitero"
# This is SKU 10300028 based on earlier logs showing 12 units sold in order #1.
p = db.query(Product).filter(Product.sku == '10300028').first()
if p:
    p.name = "Aceitero"
    p.description = "Aceitero"
    db.commit()
    print("Updated product 10300028 to Aceitero.")
else:
    print("Product 10300028 not found.")

db.close()
