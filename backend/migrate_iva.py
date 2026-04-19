from app.database import engine, SessionLocal
from app import models
from sqlalchemy import inspect
from datetime import datetime
import pytz

def get_ar_time():
    return datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))

inspector = inspect(engine)
if not inspector.has_table("capital_ivas"):
    print("Creando tabla capital_ivas...")
    models.CapitalIva.__table__.create(engine)
    print("Tabla creada.")

db = SessionLocal()
count = db.query(models.CapitalIva).count()
if count == 0:
    print("No se encontraron registros de IVA. Revisando configuración antigua...")
    old_setting = db.query(models.Settings).filter(models.Settings.key == "capital_iva_amount").first()
    if old_setting and old_setting.value:
        try:
            amount = float(old_setting.value)
            if amount > 0:
                print(f"Migrando monto antiguo: {amount}")
                new_iva = models.CapitalIva(
                    amount=amount,
                    created_at=get_ar_time(),
                    observation="Migrado del sistema anterior",
                    created_by="system"
                )
                db.add(new_iva)
                db.commit()
                print("Migración exitosa.")
        except Exception as e:
            print(f"Error migrando: {e}")
            db.rollback()
else:
    print(f"Se encontraron {count} registros de IVA. No se requiere migración.")

print("Deprecando configuración antigua...")
old_setting = db.query(models.Settings).filter(models.Settings.key == "capital_iva_amount").first()
if old_setting:
    db.delete(old_setting)
    db.commit()
    print("Configuración antigua eliminada.")

print("Completado.")
