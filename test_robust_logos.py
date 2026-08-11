import string
from pathlib import Path

def normalize(s):
    return s.strip().lower().replace(" ", "").translate(str.maketrans('', '', string.punctuation))

def robust_match(brand_name, filename_stem):
    b = normalize(brand_name)
    f = normalize(filename_stem)
    if b == f: return True
    if f in b: return True # e.g. "tooba" in "toobazaiqafoods"
    if b in f: return True
    return False

print("Tooba Zaiqa Foods vs Tooba:", robust_match("Tooba Zaiqa Foods", "Tooba"))
print("Bake Parlor vs Bake Parlor:", robust_match("Bake Parlor", "Bake Parlor"))
