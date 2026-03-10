from app.database import engine, Base
from app import models
import sqlalchemy as sa
from sqlalchemy.schema import DropConstraint, DropTable

meta = Base.metadata

with engine.begin() as conn:
    for table in reversed(meta.sorted_tables):
        conn.execute(sa.text(f'TRUNCATE TABLE "{table.name}" CASCADE;'))

print("Todas las tablas fueron truncadas exitosamente.")
