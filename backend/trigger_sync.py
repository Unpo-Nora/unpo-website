from app.database import SessionLocal
from app.utils.product_importer import sync_products_from_excel
import os

def run_sync():
    db = SessionLocal()
    try:
        excel_path = "/app/data/MAYORISTA.csv"
        print(f"Iniciando sincronización (v2) desde: {excel_path}")
        result = sync_products_from_excel(db, excel_path)
        print(f"Resultado: {result}")
    finally:
        db.close()

if __name__ == "__main__":
    run_sync()
