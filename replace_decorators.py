import os

keep_routes = [
    "def products_list",
    "def products_search",
    "def categories_list",
    "def brands_list",
    "def brands_search",
    "def sales_data",
    "def sales_next_invoice",
    "def sale_details", # Might be needed for receipts later
    "def login"
]

with open('app.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line.strip() == "@login_required":
        if i + 1 < len(lines):
            next_line = lines[i+1].strip()
            if any(next_line.startswith(route) for route in keep_routes):
                new_lines.append(line)
            else:
                new_lines.append(line.replace("@login_required", "@admin_required"))
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open('app.py', 'w') as f:
    f.writelines(new_lines)

print("Updated decorators successfully.")
