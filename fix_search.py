import re
with open("app.py", "r") as f:
    c = f.read()

c = re.sub(
    r'(warehouse_id = request\.args\.get\("warehouse_id"\)\n\s*if current_user\.role != \'admin\' and current_user\.warehouse_id:\n\s*warehouse_id = current_user\.warehouse_id)',
    r'\1\n    wid = int(warehouse_id) if warehouse_id else (current_user.warehouse_id or 1)',
    c
)

c = re.sub(
    r'(\(warehouse_id,\) if warehouse_id else \(\))',
    r'(wid,)',
    c
)

c = re.sub(
    r'(\(f"%\{q\}%", f"%\{q\}%", f"%\{q\}%", warehouse_id\) if warehouse_id else \(f"%\{q\}%", f"%\{q\}%", f"%\{q\}%"\))',
    r'(f"%{q}%", f"%{q}%", f"%{q}%", wid)',
    c
)

with open("app.py", "w") as f:
    f.write(c)
