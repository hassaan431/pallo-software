import os
import glob
from rembg import remove
from PIL import Image

brands_dir = 'static/logos/brands'
for filepath in glob.glob(os.path.join(brands_dir, '*.*')):
    filename = os.path.basename(filepath)
    name, ext = os.path.splitext(filename)
    
    # Process with rembg
    try:
        print(f"Processing {filename}...")
        input_image = Image.open(filepath)
        
        # Ensure it has an alpha channel for rembg (sometimes needed for JPEGs)
        if input_image.mode != 'RGBA':
            input_image = input_image.convert('RGBA')
            
        output_image = remove(input_image)
        
        # Overwrite or save as PNG
        output_path = os.path.join(brands_dir, f"{name}.png")
        output_image.save(output_path, "PNG")
        
        # If original wasn't PNG, remove it so we only have PNGs left
        if ext.lower() not in ['.png']:
            os.remove(filepath)
            
        print(f"Successfully processed {filename}")
    except Exception as e:
        print(f"Error processing {filename}: {e}")
