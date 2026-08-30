import re
with open("templates/inventory.html", "r") as f:
    c = f.read()

# Fix JS error
c = re.sub(
    r"document\.getElementById\('editStockQuantity'\)\.value = editBtn\.getAttribute\('data-stock-quantity'\) \|\| 0;",
    r"// document.getElementById('editStockQuantity').value = editBtn.getAttribute('data-stock-quantity') || 0;",
    c
)

# Re-add addStockQuantity to add modal if it was removed
# The modal was previously set to type="hidden". Let's change it back to visible text input, or maybe I deleted it?
# Let's check if addStockQuantity is in the file.
