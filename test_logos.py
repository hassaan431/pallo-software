import sqlite3
from database import get_brand_logo_filename, DB_PATH

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL AND brand != ''")
brands = [row[0] for row in cursor.fetchall()]
conn.close()

missing = []
for b in brands:
    logo = get_brand_logo_filename(b)
    print(f"Brand: '{b}' -> Logo: {logo}")
    if not logo:
        missing.append(b)

if missing:
    print("\nMissing logos for:")
    for m in missing:
        print(f"- '{m}'")
