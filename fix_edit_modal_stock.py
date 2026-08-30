import re
with open("templates/inventory.html", "r") as f:
    c = f.read()

# 1. Inject the Adjust Inventory row inside Edit Product modal
ui_html = """
        <div class="modal-field" style="display: flex; justify-content: space-between; align-items: center; background: #f8fafc; padding: 10px; border-radius: 6px; border: 1px solid #e2e8f0; margin-top: 10px; margin-bottom: 10px;">
          <div>
            <span style="font-weight: 600; color: #475569;">Current Inventory:</span>
            <span id="editModalCurrentStockDisplay" style="font-size: 1.1rem; font-weight: 700; color: #0f172a; margin-left: 10px;">0</span>
          </div>
          <button type="button" id="btnAdjustInventoryInEdit" class="btn btn-outline-primary" style="padding: 6px 12px; font-size: 13px;" onclick="openAdjustStockFromEdit(this)">Adjust Inventory</button>
        </div>
"""
c = c.replace(
    '        <div class="modal-field" style="display: flex; align-items: center; gap: 0.5rem; margin-top: 1rem;">\n          <input type="checkbox" id="editIsPublic"',
    ui_html + '        <div class="modal-field" style="display: flex; align-items: center; gap: 0.5rem; margin-top: 1rem;">\n          <input type="checkbox" id="editIsPublic"'
)

# 2. Add the JS handler for openAdjustStockFromEdit
js_html = """
  function openAdjustStockFromEdit(btn) {
    const id = btn.getAttribute('data-id');
    const name = btn.getAttribute('data-name');
    const stock = btn.getAttribute('data-stock');
    closeModal('editProductModal');
    openAdjustStockModal(id, name, stock);
  }
"""
c = c.replace(
    'function openAdjustStockModal(id, name, currentStock) {',
    js_html + '\n  function openAdjustStockModal(id, name, currentStock) {'
)

# 3. In the edit-product handler, populate the attributes for the button
populate_js = """
        const stockQty = editBtn.getAttribute('data-stock-quantity') || 0;
        document.getElementById('editModalCurrentStockDisplay').textContent = stockQty;
        const adjustBtn = document.getElementById('btnAdjustInventoryInEdit');
        adjustBtn.setAttribute('data-id', productId);
        adjustBtn.setAttribute('data-name', editBtn.getAttribute('data-name'));
        adjustBtn.setAttribute('data-stock', stockQty);
"""
# Replace the commented out line with this new logic
c = c.replace(
    "// document.getElementById('editStockQuantity').value = editBtn.getAttribute('data-stock-quantity') || 0;",
    populate_js
)

with open("templates/inventory.html", "w") as f:
    f.write(c)
