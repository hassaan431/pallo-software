# Scope Customers, Point of Sale and Invoicing

Type: task
Status: open
Blocked by: none (06 resolved)

## Question

How do we scope all customer ledgers, POS checkout routes, and sales history in [app.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/app.py) to `company_id = current_user.company_id`, while routing sequential invoice generation to the company's specific prefix (`INV-`, `AK-`) and sequence counter via `get_next_invoice_number(company_id)`?
