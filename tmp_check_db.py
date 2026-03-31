import sys
sys.path.append('backend')
from sqlalchemy import create_engine, text

# Conectando a localhost en lugar de 'db'
engine = create_engine('postgresql://unpo_admin:secure_password_123@localhost:5432/unpo_nora_db')

with engine.connect() as conn:
    try:
        # Check SKU 20700051 specifically
        sku = '20700051'
        print(f"Checking SKU {sku}...")
        result = conn.execute(text(f"SELECT sku, name, is_active, stock_quantity FROM products WHERE sku='{sku}'"))
        rows = result.fetchall()
        for row in rows:
            print(f"SKU {sku} details: {row}")
        
        # Check total active products with stock
        print("\nChecking total active products with stock > 0...")
        result = conn.execute(text("SELECT count(*) FROM products WHERE is_active = true AND stock_quantity > 0"))
        count = result.scalar()
        print(f"Total active with stock: {count}")
        
        # Check first 5 active with stock
        if count > 0:
            print("\nFirst 5 active with stock:")
            result = conn.execute(text("SELECT sku, name, is_active, stock_quantity FROM products WHERE is_active = true AND stock_quantity > 0 LIMIT 5"))
            for row in result.fetchall():
                print(row)
                
    except Exception as e:
        print("Error:", e)
