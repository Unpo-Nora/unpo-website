import sqlite3
import datetime

def migrate():
    conn = sqlite3.connect('unpo_nora.db')
    c = conn.cursor()

    # 1. Ensure table exists (SQLAlchemy might create it, but we can too)
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='capital_ivas'")
    if not c.fetchone():
        c.execute('''
            CREATE TABLE capital_ivas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount NUMERIC(12, 2) NOT NULL,
                created_at DATETIME,
                observation VARCHAR,
                created_by VARCHAR
            )
        ''')
        c.execute('CREATE INDEX ix_capital_ivas_id ON capital_ivas (id)')

    # 2. Check if records exist
    c.execute('SELECT COUNT(*) FROM capital_ivas')
    count = c.fetchone()[0]
    if count == 0:
        c.execute("SELECT value FROM settings WHERE key='capital_iva_amount'")
        row = c.fetchone()
        if row and row[0]:
            try:
                amount = float(row[0])
                if amount > 0:
                    now = datetime.datetime.now().isoformat()
                    c.execute("INSERT INTO capital_ivas (amount, created_at, observation, created_by) VALUES (?, ?, ?, ?)", 
                              (amount, now, "Migrado del sistema anterior", "system"))
                    print(f"Migrated amount: {amount}")
            except Exception as e:
                print(f"Error parsing amount: {e}")

    # 3. Delete old setting
    c.execute("DELETE FROM settings WHERE key='capital_iva_amount'")
    
    conn.commit()
    conn.close()
    print("Migration finished successfully.")

if __name__ == '__main__':
    migrate()
