from PIL import Image
import glob
import os

for img_path in glob.glob("static/logos/brands/*.png"):
    try:
        im = Image.open(img_path)
        im = im.convert("RGBA")
        
        # Get bounding box of non-transparent pixels
        bbox = im.getbbox()
        if bbox:
            im = im.crop(bbox)
            im.save(img_path)
            print(f"Trimmed {img_path}")
    except Exception as e:
        print(f"Error on {img_path}: {e}")
