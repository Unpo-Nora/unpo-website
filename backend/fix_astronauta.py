from app.database import engine
from sqlalchemy import text

with engine.begin() as conn:
    conn.execute(text("UPDATE products SET images='[\"/static/images/10300074_1.jpg\", \"/static/images/10300074_2.jpg\"]' WHERE sku='10300074'"))
    print("Images updated")
