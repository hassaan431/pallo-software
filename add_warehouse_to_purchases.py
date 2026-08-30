import re
with open("templates/purchases.html", "r") as f:
    c = f.read()

c = re.sub(
    r'(<th>Reference #</th>)',
    r'\1\n            <th>Warehouse</th>',
    c
)

c = re.sub(
    r'(<td>\{\{ p\.reference_number \}\}</td>)',
    r'\1\n            <td style="color: #6b7280; font-size: 0.9em;">{{ p.warehouse_name or "Main Warehouse" }}</td>',
    c
)

with open("templates/purchases.html", "w") as f:
    f.write(c)
