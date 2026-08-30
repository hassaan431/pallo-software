import re
with open("templates/inventory.html", "r") as f:
    c = f.read()

# Remove stock from addProductForm
c = re.sub(
    r'<div class="modal-field">\s*<label for="addStock">Initial Stock.*?</label>\s*<input type="number" step="any" class="form-control" id="addStock" name="stock_quantity" value="0">\s*</div>',
    r'',
    c, flags=re.DOTALL
)

# Remove stock from editProductForm
c = re.sub(
    r'<div class="modal-field">\s*<label for="editStock">Current Stock</label>\s*<input type="number" step="any" class="form-control" id="editStock" name="stock_quantity" required>\s*</div>',
    r'',
    c, flags=re.DOTALL
)

with open("templates/inventory.html", "w") as f:
    f.write(c)
