# Scope Products, Categories and Inventory with Cost Price Masking

Type: task
Status: open
Blocked by: 04

## Question

How do we update all inventory, product, category, brand, and stock adjustment endpoints in [app.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/app.py) to scope records by `current_user.company_id`, while strictly redacting `cost_price` and profit margin data when accessed by non-admin roles (`salesman`, `warehouse_manager`) as mandated by ADR 0003?
