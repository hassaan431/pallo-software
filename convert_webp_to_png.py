import os
import sqlite3
from pathlib import Path
from PIL import Image

def main():
    base_dir = Path('/Users/hassaanjazz/Desktop/Projects/Inventory and Invoice Software')
    products_dir = base_dir / 'static' / 'uploads' / 'products'
    db_path = base_dir / 'database.db'
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    count = 0
    for webp_path in products_dir.glob('*.webp'):
        png_path = webp_path.with_suffix('.png')
        try:
            with Image.open(webp_path) as img:
                img.save(png_path, 'PNG')
            
            # Update DB
            old_url = f"/static/uploads/products/{webp_path.name}"
            new_url = f"/static/uploads/products/{png_path.name}"
            
            cur.execute("UPDATE products SET image_url = ? WHERE image_url = ?", (new_url, old_url))
            
            # Delete original webp
            webp_path.unlink()
            count += 1
            print(f"Converted {webp_path.name} to {png_path.name}")
        except Exception as e:
            print(f"Error converting {webp_path.name}: {e}")
            
    conn.commit()
    conn.close()
    print(f"Total converted: {count}")

if __name__ == '__main__':
    main()
