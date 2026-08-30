import re
with open("templates/inventory.html", "r") as f:
    c = f.read()

# Fix the duplicate sellEl line
c = c.replace(
    "}if (sellEl) sellEl.value = '';\n      if (sellEl) sellEl.value = '';",
    "}if (sellEl) sellEl.value = '';"
)

with open("templates/inventory.html", "w") as f:
    f.write(c)
