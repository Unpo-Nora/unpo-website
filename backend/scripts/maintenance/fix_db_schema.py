"""
[MANTENIMIENTO MANUAL — NO runtime]

Parche de esquema puntual: agrega columnas faltantes y crea tablas nuevas si no
existen. Reubicado desde el endpoint HTTP `GET /fix_db_schema` (removido en la
Etapa 6-B2 por ser un GET público sin auth que ejecutaba DDL).

- NO se ejecuta por import (todo el trabajo está en run(), bajo __main__).
- NO está conectado a FastAPI.
- Muta el esquema de la DB apuntada por DATABASE_URL. Correr a conciencia.

Uso:
    cd backend && python -m scripts.maintenance.fix_db_schema
"""


def run():
    # Imports locales: importar este módulo NO debe conectar ni requerir el paquete `app`.
    from sqlalchemy import text
    from app.database import SessionLocal, engine, Base
    from app.models import Employee, InventoryAuditLog

    db = SessionLocal()
    errors = []
    try:
        try:
            db.execute(text('ALTER TABLE products ADD COLUMN price_breakdown JSON;'))
            db.commit()
        except Exception as e:
            db.rollback()
            errors.append(f"products.price_breakdown error: {e}")

        try:
            db.execute(text('ALTER TABLE expenses ADD COLUMN user_email VARCHAR;'))
            db.commit()
        except Exception as e:
            db.rollback()
            errors.append(f"expenses.user_email error: {e}")

        try:
            Base.metadata.tables[Employee.__tablename__].create(engine, checkfirst=True)
            Base.metadata.tables[InventoryAuditLog.__tablename__].create(engine, checkfirst=True)
        except Exception as e:
            errors.append(f"Table creation error: {e}")
    finally:
        db.close()

    print({"status": "done", "message": "Database schema patch executed", "errors": str(errors)})


if __name__ == "__main__":
    run()
