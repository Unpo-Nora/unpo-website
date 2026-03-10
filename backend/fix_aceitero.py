from app.database import engine
from sqlalchemy import text

with engine.begin() as conn:
    name = "Aceitero/Vinagrero de vidrio"
    desc = "Aceitero/Vinagrero de vidrio de 300ml de capacidad, pico de plástico con cierre tapón."
    # Fix escaping
    sql = text("UPDATE products SET name=:n, description=:d WHERE sku='10300028'")
    conn.execute(sql, {"n": name, "d": desc})
    print("Producto Aceitero actualizado correctamente")
