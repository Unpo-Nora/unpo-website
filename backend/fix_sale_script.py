from app.database import SessionLocal
from app.models import Product, OrderItem, SaleOrder

db = SessionLocal()

print("--- ELEFANTES ---")
elefantes = db.query(Product).filter(Product.name.ilike('%elefante%')).all()
for e in elefantes:
    print(f"{e.sku} - {e.name}")

print("\n--- ACEITEROS ---")
aceiteros = db.query(Product).filter(Product.name.ilike('%aceit%')).all()
for a in aceiteros:
    print(f"{a.sku} - {a.name}")

print("\n--- RECENT ORDERS PORTING ELEFANTE ---")
elefante_sku = "10300028" # Guessing from earlier output if visible, but let's just query
for e in elefantes:
    orders = db.query(OrderItem).filter(OrderItem.product_sku == e.sku).all()
    for o in orders:
        print(f"Order ID: {o.order_id}, Item ID: {o.id}, Qty: {o.quantity}, SKU: {o.product_sku}, Price: {o.total_price}")

db.close()
