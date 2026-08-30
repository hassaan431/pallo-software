import re
with open("app.py", "r") as f:
    c = f.read()

c = re.sub(
    r'(all_users=users_list,\n\s*\))',
    r'\1\n        warehouses=warehouses_list,',
    c
)

c = re.sub(
    r'(all_users=users_list,\n\s*warehouses=warehouses_list,\n\s*\))',
    r'all_users=users_list,\n        warehouses=warehouses_list\n    )',
    c
)

with open("app.py", "w") as f:
    f.write(c)
