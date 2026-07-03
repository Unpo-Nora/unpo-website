# Scripts de mantenimiento manual

⚠️ **MANTENIMIENTO MANUAL — NO se ejecutan en runtime.**

Estos scripts contienen lógica que **antes** vivía como endpoints HTTP GET públicos en
`backend/app/main.py` (`/fix_*`, `/migrate_*`). En la Etapa 6-B2 (hardening previo a AWS)
esos endpoints se **removieron de la superficie HTTP** porque eran GET sin autenticación
que mutaban/borraban datos, y se reubicó acá la lógica que todavía puede servir.

Reglas:

- **No** están conectados a FastAPI. No hay ninguna ruta HTTP que los invoque.
- **No** se ejecutan por import: todo el trabajo está dentro de `run()` y sólo corre
  bajo `if __name__ == "__main__":`. Importar el módulo no tiene efectos secundarios.
- Son **one-off / correctivos**. Corrélos a conciencia, apuntando `DATABASE_URL` a la DB
  objetivo, y sólo si sabés que hacen falta.
- Mutan datos: **no** los corras contra producción sin backup y sin revisar la lógica.

Ejecución (manual, desde `backend/`, con `DATABASE_URL` seteada):

```bash
cd backend
python -m scripts.maintenance.fix_db_schema
python -m scripts.maintenance.migrate_finance_schema_and_data
python -m scripts.maintenance.fix_valija_category
python -m scripts.maintenance.migrate_capital_iva_system
```

A futuro, esta lógica correctiva/estructural debería migrar a Alembic (pendiente:
resolver los dos heads de migraciones).
