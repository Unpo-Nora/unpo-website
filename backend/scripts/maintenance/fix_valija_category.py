"""
[MANTENIMIENTO MANUAL — NO runtime]

Reasigna los productos de la categoria "Valija" a "Bazar" (creandola si no existe)
y elimina la categoria "Valija". Reubicado desde el endpoint HTTP
`GET /fix_valija_category` (removido en la Etapa 6-B2).

- NO se ejecuta por import (todo el trabajo está en run(), bajo __main__).
- NO está conectado a FastAPI.
- Muta y BORRA datos en la DB apuntada por DATABASE_URL. Correr a conciencia.

Uso:
    cd backend && python -m scripts.maintenance.fix_valija_category
"""


def run():
    from app.database import SessionLocal
    from app import models

    db = SessionLocal()
    try:
        valija = db.query(models.Category).filter(models.Category.name.ilike('%VALIJA%')).first()
        bazar = db.query(models.Category).filter(models.Category.name.ilike('%BAZAR%')).first()

        if not bazar:
            bazar = models.Category(name="Bazar")
            db.add(bazar)
            db.commit()
            db.refresh(bazar)

        fixed_count = 0
        if valija:
            products = db.query(models.Product).filter(models.Product.category_id == valija.id).all()
            for p in products:
                p.category_id = bazar.id
                fixed_count += 1
            db.delete(valija)
            db.commit()

        p_ban = db.query(models.Product).filter(models.Product.name.ilike('%bandeja cuadrada%')).first()
        if p_ban and p_ban.category_id != bazar.id:
            p_ban.category_id = bazar.id
            db.commit()
            fixed_count += 1

        print(f"Migrated {fixed_count} products. Valija category removed. new_category={bazar.id}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
