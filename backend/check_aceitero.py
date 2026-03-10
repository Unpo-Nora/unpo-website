from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    print("--- Buscando producto llamado 'Aceitero' ---")
    res1 = conn.execute(text("SELECT sku, name, description FROM products WHERE name ILIKE '%Aceitero%'")).fetchall()
    for r in res1:
        print(f"SKU: {r[0]}, Name: {r[1]}, Desc: {r[2]}")
        
    print("\n--- Buscando producto con SKU '10300028' ---")
    res2 = conn.execute(text("SELECT sku, name, description FROM products WHERE sku='10300028'")).fetchall()
    for r in res2:
        print(f"SKU: {r[0]}, Name: {r[1]}, Desc: {r[2]}")
