import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Add new columns if not exist
try:
    cursor.execute("ALTER TABLE tasks ADD COLUMN submitted_at TEXT")
except:
    pass

try:
    cursor.execute("ALTER TABLE tasks ADD COLUMN rated_at TEXT")
except:
    pass

conn.commit()
conn.close()
print("✅ Columns added successfully")
