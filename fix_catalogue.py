import re
with open("templates/catalogue.html", "r") as f:
    c = f.read()

# Add warehouse dropdown after pos-header
c = re.sub(
    r'(<div class="pos-header">[\s\S]*?</div>)',
    r'\1\n      {% if current_user.role == "admin" %}\n      <div style="padding: 1rem 1.5rem 0; display:flex; justify-content:flex-end;">\n        <select id="warehouseSelect" class="form-control" style="width:200px;" onchange="loadProducts()">\n          {% for w in warehouses %}\n            <option value="{{ w.id }}">{{ w.name }}</option>\n          {% endfor %}\n        </select>\n      </div>\n      {% endif %}',
    c
)

c = re.sub(
    r'(fetch\(\'/products/list\'\)\.then\(r => r\.json\(\)\),)',
    r'fetch(`/products/list?warehouse_id=${document.getElementById("warehouseSelect") ? document.getElementById("warehouseSelect").value : ""}`).then(r => r.json()),',
    c
)

# And if there is any other fetch('/products/search...
c = re.sub(
    r'(fetch\(`/products/search\?q=\$\{encodeURIComponent\(query\)\}`\))',
    r'fetch(`/products/search?q=${encodeURIComponent(query)}&warehouse_id=${document.getElementById("warehouseSelect") ? document.getElementById("warehouseSelect").value : ""}`)',
    c
)

# Add loadProducts function
c = re.sub(
    r'(async function init\(\) \{)',
    r'async function loadProducts() {\n      try {\n        const prodRes = await fetch(`/products/list?warehouse_id=${document.getElementById("warehouseSelect") ? document.getElementById("warehouseSelect").value : ""}`).then(r => r.json());\n        products = prodRes;\n        renderProducts(products);\n      } catch (e) { console.error(e); }\n    }\n\n    \1',
    c
)

with open("templates/catalogue.html", "w") as f:
    f.write(c)
