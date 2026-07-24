import re

with open('app.py', 'r') as f:
    content = f.read()

# Pattern for s.status followed by FROM sales s
pattern = r'(s\.status\s+)(FROM sales s)'

# Replacement
replacement = r'\1, u.username AS salesman_name\n            \2\n            LEFT JOIN users u ON u.id = s.salesman_id'

# Using regex replace, but wait, it might be safer to replace EXACT strings.
# The query in reports is:
"""
                s.status
            FROM sales s
"""

content = content.replace(
    "                s.status\n            FROM sales s",
    "                s.status,\n                u.username AS salesman_name\n            FROM sales s\n            LEFT JOIN users u ON u.id = s.salesman_id"
)

with open('app.py', 'w') as f:
    f.write(content)

print("Patched reports invoices queries.")
