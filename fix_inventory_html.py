import re
with open("templates/inventory.html", "r") as f:
    c = f.read()

c = re.sub(
    r'(<form action="/inventory" method="GET" style="display: flex; gap: 0\.5rem; align-items: center; flex-wrap: wrap;">)',
    r'\1\n      {% if current_user.role == "admin" %}\n      <select name="warehouse_id" class="form-control" style="width: auto; padding: 0.25rem 0.5rem; height: auto;" onchange="this.form.submit()">\n        <option value="">All Warehouses</option>\n        {% for w in warehouses %}\n          <option value="{{ w.id }}" {% if current_warehouse_id == w.id %}selected{% endif %}>{{ w.name }}</option>\n        {% endfor %}\n      </select>\n      {% endif %}',
    c
)

with open("templates/inventory.html", "w") as f:
    f.write(c)
