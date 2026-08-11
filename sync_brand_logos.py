import os
import shutil
import sqlite3
from pathlib import Path

def sync_logos():
    base_dir = Path(__file__).resolve().parent
    brands_dir = base_dir / "static" / "logos" / "brands"
    db_path = base_dir / "database.db"
    
    if not db_path.exists():
        print("database.db not found")
        return
        
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL AND brand != ''")
    db_brands = [row[0] for row in cur.fetchall()]
    conn.close()
    
    print("DB Brands:", db_brands)
    
    existing_files = {f.name: f for f in brands_dir.glob("*.png")}
    print("Existing files:", list(existing_files.keys()))
    
    for brand in db_brands:
        target_name = f"{brand}.png"
        target_path = brands_dir / target_name
        
        if target_path.exists():
            print(f"OK: {target_name} exists")
            continue
            
        # Try to find case-insensitive match
        brand_lower = brand.strip().lower()
        found = False
        for fname, fpath in existing_files.items():
            if fpath.stem.strip().lower() == brand_lower:
                shutil.copy2(fpath, target_path)
                print(f"COPIED: {fname} -> {target_name}")
                found = True
                break
                
        if not found:
            print(f"WARNING: No logo found for brand '{brand}'")

if __name__ == "__main__":
    sync_logos()
