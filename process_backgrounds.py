"""
CLI utility to scan product images for backgrounds and remove backgrounds using rembg.

Usage:
    python3 process_backgrounds.py --check
    python3 process_backgrounds.py --dry-run
    python3 process_backgrounds.py --process --limit 5
    python3 process_backgrounds.py --process --all
    python3 process_backgrounds.py --file static/uploads/products/sample.png
"""

import os
import sys
import argparse
import shutil
from PIL import Image

PRODUCTS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'products')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'products_backup')
BROCHURE_CACHE_DIR = os.path.join(os.path.dirname(__file__), 'static', 'brochure_cache')

def check_image_transparency(filepath):
    """
    Returns True if image already has transparent areas, False if opaque/has background.
    """
    try:
        with Image.open(filepath) as img:
            if img.mode in ('RGBA', 'LA') or ('transparency' in img.info):
                alpha = img.convert('RGBA').split()[-1]
                min_alpha, _ = alpha.getextrema()
                # If minimum alpha is less than 250, there are transparent pixels
                return min_alpha < 250
            return False
    except Exception as e:
        return None

def scan_images():
    """
    Scans the product images directory and classifies them.
    """
    if not os.path.exists(PRODUCTS_DIR):
        print(f"[!] Products directory not found: {PRODUCTS_DIR}")
        return [], []

    valid_exts = ('.png', '.jpg', '.jpeg', '.webp')
    files = sorted([f for f in os.listdir(PRODUCTS_DIR) if f.lower().endswith(valid_exts)])

    transparent_list = []
    has_bg_list = []

    for f in files:
        full_path = os.path.join(PRODUCTS_DIR, f)
        is_transparent = check_image_transparency(full_path)
        if is_transparent is True:
            transparent_list.append(full_path)
        elif is_transparent is False:
            has_bg_list.append(full_path)

    return transparent_list, has_bg_list

def remove_background(filepath, session=None, backup=True):
    """
    Removes background from a single image using rembg.
    Saves as RGBA PNG.
    """
    import rembg

    if backup:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_file = os.path.join(BACKUP_DIR, os.path.basename(filepath))
        if not os.path.exists(backup_file):
            shutil.copy2(filepath, backup_file)

    with Image.open(filepath) as img:
        img_rgba = img.convert('RGBA')
        if session:
            output = rembg.remove(img_rgba, session=session)
        else:
            output = rembg.remove(img_rgba)

    # Save output to original path
    output.save(filepath, format="PNG")
    return True

def clear_brochure_cache():
    if os.path.exists(BROCHURE_CACHE_DIR):
        count = 0
        for f in os.listdir(BROCHURE_CACHE_DIR):
            file_path = os.path.join(BROCHURE_CACHE_DIR, f)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    count += 1
                except Exception:
                    pass
        if count > 0:
            print(f"[*] Cleared {count} cached thumbnails in brochure cache.")

def main():
    parser = argparse.ArgumentParser(description="Scan and remove backgrounds from product images.")
    parser.add_argument('--check', action='store_true', help="Check which images have backgrounds without making changes.")
    parser.add_argument('--process', action='store_true', help="Remove backgrounds from images.")
    parser.add_argument('--all', action='store_true', help="Process all images that have backgrounds.")
    parser.add_argument('--limit', type=int, default=0, help="Limit number of images to process.")
    parser.add_argument('--file', type=str, help="Process a specific image file.")
    parser.add_argument('--no-backup', action='store_true', help="Do not create backups before modifying images.")

    args = parser.parse_args()

    if args.check:
        print("\n=== SCANNING PRODUCT IMAGES ===")
        transparent, has_bg = scan_images()
        print(f"Total images found: {len(transparent) + len(has_bg)}")
        print(f"  - Already transparent: {len(transparent)}")
        print(f"  - Needs background removed: {len(has_bg)}")
        if has_bg:
            print("\nImages with background:")
            for p in has_bg[:15]:
                print(f"  [HAS BACKGROUND] {os.path.basename(p)}")
            if len(has_bg) > 15:
                print(f"  ... and {len(has_bg) - 15} more.")
        return

    if args.file:
        if not os.path.exists(args.file):
            print(f"[-] File not found: {args.file}")
            sys.exit(1)
        print(f"[*] Processing single file: {args.file}")
        try:
            remove_background(args.file, backup=not args.no_backup)
            print(f"[+] Successfully removed background: {args.file}")
            clear_brochure_cache()
        except Exception as e:
            print(f"[-] Error removing background: {e}")
            sys.exit(1)
        return

    if args.process:
        transparent, has_bg = scan_images()
        to_process = has_bg
        if args.limit > 0:
            to_process = to_process[:args.limit]

        if not to_process:
            print("[+] No images needing background removal!")
            return

        print(f"\n[*] Preparing to remove background from {len(to_process)} image(s)...")
        print(f"[*] Original backups will be stored in: {BACKUP_DIR}")
        
        try:
            import rembg
            # Create a reusable session so the AI model is loaded only once
            session = rembg.new_session()
        except ImportError:
            print("[-] 'rembg' is not installed. Run: pip install rembg")
            sys.exit(1)

        success_count = 0
        for idx, img_path in enumerate(to_process, 1):
            fname = os.path.basename(img_path)
            print(f"[{idx}/{len(to_process)}] Processing {fname}...", end="", flush=True)
            try:
                remove_background(img_path, session=session, backup=not args.no_backup)
                print(" DONE")
                success_count += 1
            except Exception as e:
                print(f" FAILED ({e})")

        print(f"\n[+] Successfully processed {success_count}/{len(to_process)} images.")
        clear_brochure_cache()
        return

    parser.print_help()

if __name__ == '__main__':
    main()
