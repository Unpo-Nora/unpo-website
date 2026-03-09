import sys
import os
import logging

logging.basicConfig(level=logging.INFO)

print("Starting sync run script...")
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.utils.product_importer import sync_products_from_excel

db = SessionLocal()
print("Connected to DB.")

try:
    print("Running sync...")
    result = sync_products_from_excel(db, 'data/MAYORISTA.csv')
    print("Result:", result)
finally:
    db.close()
    print("Done.")
