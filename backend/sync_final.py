import sys
import os

# Forzar path para encontrar el paquete app
sys.path.append(os.getcwd())

try:
    from app.database import SessionLocal
    from app.utils.product_importer import sync_products_from_excel
    
    print("Iniciando Sincronización Final...")
    db = SessionLocal()
    # No importa el path del excel si el importador usa los CSVs fijos
    res = sync_products_from_excel(db, '/app/data/Panel_control_UNPO.xlsm')
    print("RESULTADO:", res)
    db.close()
except Exception as e:
    print("ERROR FATAL:", e)
    import traceback
    traceback.print_exc()
