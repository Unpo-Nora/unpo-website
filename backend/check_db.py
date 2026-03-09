from app.database import SessionLocal
from app.models import Product, User

def check_db():
    db = SessionLocal()
    try:
        products = db.query(Product).all()
        print(f"Total productos en DB: {len(products)}")
        with open('db_dump.txt', 'w', encoding='utf-8') as f:
            for p in products:
                f.write(f"SKU: {p.sku} | Nombre: {p.name[:50]} | Stock: {p.stock_quantity} | Precio: {p.price_wholesale}\n")
        print("Done")
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
