import sqlite3
import pandas as pd

conn = sqlite3.connect('backend/unpo_nora.db')
cursor = conn.cursor()

# Get tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", tables)

# Get users
try:
    df = pd.read_sql_query("SELECT id, email, is_active, is_superuser, role FROM users", conn)
    print("Users table:")
    print(df)
except Exception as e:
    print("Error querying users table:", e)

# Also check users table if it's named 'user'
try:
    df = pd.read_sql_query("SELECT id, email, is_active, is_superuser, role FROM user", conn)
    print("User table:")
    print(df)
except Exception as e:
    print("Error querying user table:", e)
    
conn.close()
