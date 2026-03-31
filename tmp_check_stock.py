from app.database import SessionLocal
from app import models

db = SessionLocal()
try:
    sku = "20700051"
    product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if product:
        print(f"Product: {product.name}")
        print(f"SKU: {product.sku}")
        print(f"Is Active: {product.is_active}")
        print(f"Stock: {product.stock_quantity}")
    else:
        print(f"Product with SKU {sku} not found.")

    # Check first 5 active products with stock
    active_with_stock = db.query(models.Product).filter(
        models.Product.is_active == True,
        models.Product.stock_quantity > 0
    ).limit(5).all()
    print("\nActive products with stock (first 5):")
    for p in active_with_stock:
        print(f"- {p.name} (SKU: {p.sku}, Stock: {p.stock_quantity})")

    # Check total count
    total_active_stock = db.query(models.Product).filter(
        models.Product.is_active == True,
        models.Product.stock_quantity > 0
    ).count()
    print(f"\nTotal active products with stock: {total_active_stock}")

finally:
    db.close()
