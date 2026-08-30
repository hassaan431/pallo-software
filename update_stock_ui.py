import re
with open("templates/inventory.html", "r") as f:
    c = f.read()

# Add edit button next to qty_int
c = re.sub(
    r'<td>\{\{ qty_int \}\}</td>',
    r'<td>{{ qty_int }} <button class="btn btn-sm btn-outline-primary" style="padding: 2px 5px; font-size: 10px; margin-left: 5px;" onclick="openAdjustStockModal({{ p.id }}, \'{{ p.name|e }}\', {{ qty_int }})" title="Adjust Stock"><i class="fas fa-edit"></i></button></td>',
    c
)

# Add modal HTML before editProductModal
modal_html = """
  <!-- Adjust Stock Modal -->
  <div class="modal-overlay" id="adjustStockModal">
    <div class="modal">
      <div class="modal-header">
        <h3>Adjust Stock: <span id="adjustStockProductName"></span></h3>
        <button class="modal-close" onclick="closeModal('adjustStockModal')">&times;</button>
      </div>
      <form id="adjustStockForm" method="post" action="/inventory/adjust_stock">
        <input type="hidden" id="adjustStockProductId" name="product_id">
        <div class="modal-field">
          <label>Current Stock</label>
          <input type="number" class="form-control" id="adjustStockCurrent" readonly style="background: #f3f4f6;">
        </div>
        <div class="modal-field">
          <label for="adjustStockNew">New Stock Quantity</label>
          <input type="number" step="any" class="form-control" id="adjustStockNew" name="new_stock" required>
        </div>
        <div class="modal-field" style="display:none;">
          <input type="hidden" name="warehouse_id" value="{{ current_warehouse_id }}">
        </div>
        <div class="modal-footer">
          <button type="button" class="btn" onclick="closeModal('adjustStockModal')">Cancel</button>
          <button type="submit" class="btn btn-primary">Save Adjustment</button>
        </div>
      </form>
    </div>
  </div>
"""

c = c.replace('<!-- Edit Product Modal -->', modal_html + '\n  <!-- Edit Product Modal -->')

# Add openAdjustStockModal function to script
script_html = """
  function openAdjustStockModal(id, name, currentStock) {
    document.getElementById('adjustStockProductId').value = id;
    document.getElementById('adjustStockProductName').textContent = name;
    document.getElementById('adjustStockCurrent').value = currentStock;
    document.getElementById('adjustStockNew').value = currentStock;
    document.getElementById('adjustStockModal').classList.add('active');
  }
"""

c = c.replace('function filterProductsTable() {', script_html + '\n  function filterProductsTable() {')

with open("templates/inventory.html", "w") as f:
    f.write(c)
