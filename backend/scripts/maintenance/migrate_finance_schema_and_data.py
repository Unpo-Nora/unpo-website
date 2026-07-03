"""
[MANTENIMIENTO MANUAL — NO runtime]

Migra los `Expense` antiguos a `FinancialTransaction` (evitando duplicados por
monto/descripcion/fecha). Reubicado desde el endpoint HTTP
`GET /migrate_finance_schema_and_data` (removido en la Etapa 6-B2).

- NO se ejecuta por import (todo el trabajo está en run(), bajo __main__).
- NO está conectado a FastAPI.
- Inserta filas en la DB apuntada por DATABASE_URL. Correr a conciencia.

Uso:
    cd backend && python -m scripts.maintenance.migrate_finance_schema_and_data
"""


def run():
    from app.database import SessionLocal, engine
    from app import models

    db = SessionLocal()
    try:
        # Asegura que las tablas existan.
        models.Base.metadata.create_all(bind=engine)

        expenses = db.query(models.Expense).all()
        migrated_count = 0

        for exp in expenses:
            existing = db.query(models.FinancialTransaction).filter(
                models.FinancialTransaction.monto == exp.amount,
                models.FinancialTransaction.descripcion == exp.description,
                models.FinancialTransaction.fecha == exp.date,
            ).first()

            if not existing:
                tx = models.FinancialTransaction(
                    tipo_movimiento=models.TransactionType.EGRESO,
                    categoria=models.TransactionCategory.OPERATIVO,
                    descripcion=exp.description,
                    monto=exp.amount,
                    moneda="ARS",
                    fecha=exp.date,
                    estado=models.TransactionStatus.PAGADO,
                    created_at=exp.date,
                )
                db.add(tx)
                migrated_count += 1

        db.commit()
        print(f"Successfully migrated {migrated_count} expenses to FinancialTransaction.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
