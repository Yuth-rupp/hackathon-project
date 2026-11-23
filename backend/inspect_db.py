
import sqlite3
import json

db = sqlite3.connect("floodpulse.db")
db.row_factory = sqlite3.Row

tables = db.execute("""
    SELECT name FROM sqlite_master
    WHERE type = 'table'
    ORDER BY name
""").fetchall()

print("\n========== DATABASE TABLES ==========")

for table in tables:
    name = table["name"]
    print(f"\nTABLE: {name}")

    columns = db.execute(f'PRAGMA table_info("{name}")').fetchall()
    print("COLUMNS:", [c["name"] for c in columns])

    rows = db.execute(f'SELECT * FROM "{name}" LIMIT 2').fetchall()
    print("SAMPLE RECORDS:")
    for row in rows:
        print(json.dumps(dict(row), indent=2, default=str))

db.close()
