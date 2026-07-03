"""
[MANTENIMIENTO MANUAL — NO runtime]

Migra el monto de IVA del sistema viejo (Settings key "capital_iva_amount") a la
tabla `CapitalIva`, y elimina el setting viejo. Reubicado desde el endpoint HTTP
`GET /migrate_capital_iva_system` (removido en la Etapa 6-B2).

- NO se ejecuta por import (todo el trabajo está en run(), bajo __main__).
- NO está conectado a FastAPI.
- Muta y BORRA datos en la DB apuntada por DATABASE_URL. Correr a conciencia.

Uso:
    cd backend && python -m scripts.maintenance.migrate_capital_iva_system
"""


def run():
    from app.database import SessionLocal, engine
    from app import models

    db = SessionLocal()
    try:
        models.Base.metadata.create_all(bind=engine)

        count = db.query(models.CapitalIva).count()
        if count == 0:
            old_setting = db.query(models.Settings).filter(
                models.Settings.key == "capital_iva_amount"
            ).first()
            if old_setting and old_setting.value:
                try:
                    amount = float(old_setting.value)
                    if amount > 0:
                        from datetime import datetime
                        import pytz
                        now = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))
                        new_iva = models.CapitalIva(
                            amount=amount,
                            created_at=now,
                            observation="Migrado del sistema anterior",
                            created_by="system",
                        )
                        db.add(new_iva)
                        db.delete(old_setting)
                        db.commit()
                        print(f"Migrated amount {amount} successfully.")
                except Exception as ex:
                    print(f"Error parsing amount: {ex}")
            else:
                print("No old data to migrate.")
        else:
            old_setting = db.query(models.Settings).filter(
                models.Settings.key == "capital_iva_amount"
            ).first()
            if old_setting:
                db.delete(old_setting)
                db.commit()
            print("Migration already performed.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
