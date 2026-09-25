import os
def replace_in_file(filepath, replacements):
    with open(filepath, "r") as f:
        content = f.read()
    for old, new in replacements:
        content = content.replace(old, new)
    with open(filepath, "w") as f:
        f.write(content)

base = "../ak-distributors-public-web/src/"

# 1. page.tsx
replace_in_file(base + "app/page.tsx", [
    ("California's", "California&apos;s"),
    ("(b: any)", "(b: { logo_url?: string })"),
    ("(p: any)", "(p: { image_url?: string, name?: string, brand?: string, category_name?: string })")
])

# 2. products/page.tsx
replace_in_file(base + "app/products/page.tsx", [
    ("(p: any)", "(p: { id: number, name: string, brand?: string, category_name?: string, image_url?: string })")
])

# 3. components/BrandCarousel.tsx
replace_in_file(base + "components/BrandCarousel.tsx", [
    ("(brand: any)", "(brand: { id: number, name: string, logo_url?: string })")
])

# 4. Remove unused imports in Navbar
replace_in_file(base + "components/Navbar.tsx", [
    ("import { Button } from \"@/components/ui/button\";", ""),
    ("import { Menu, X, ShoppingCart, Search } from \"lucide-react\";", "import { Menu, ShoppingCart, Search } from \"lucide-react\";")
])

# 5. Remove unused import in About page
replace_in_file(base + "app/about/page.tsx", [
    ("import { CheckCircle2, Factory, Globe2, ShieldCheck, Users2 } from \"lucide-react\";", "import { Factory, Globe2, ShieldCheck, Users2 } from \"lucide-react\";")
])

print("Fixed ESLint errors")
