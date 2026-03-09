import pandas as pd
from app.db.session import SessionLocal
from app.utils.product_importer import sync_products_from_excel
import os

excel_path = '/app/data/Panel_control_UNPO.xlsm'
db = SessionLocal()

# Mocking a limited version of the sync or just reading fewer rows if possible
# Since sync_products_from_excel is already defined, I'll just run it.
# To make it fast, I'll temporarily patch it to read only 50 rows.
import app.utils.product_importer as importer
import builtins

original_read_excel = pd.read_excel

def limited_read_excel(*args, **kwargs):
    if 'nrows' not in kwargs:
        kwargs['nrows'] = 100 # Limit to 100 rows for speed
    return original_read_excel(*args, **kwargs)

pd.read_excel = limited_read_excel

print("Starting Fast Sync (Limited to 100 rows per sheet)...")
try:
    results = sync_products_from_excel(db, excel_path)
    print(f"Sync Results: {results}")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
