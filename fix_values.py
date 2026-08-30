import re
with open("app.py", "r") as f:
    c = f.read()

# Fix the INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) to have 13 ?
c = re.sub(
    r'(INSERT INTO sales\s*\([\s\S]*?warehouse_id\)\s*VALUES\s*\(\?, \?, \?, \?, \?, \?, \?, \?, \?, \?, \?, \?)(\))',
    r'\1, ?\2',
    c
)
with open("app.py", "w") as f:
    f.write(c)
