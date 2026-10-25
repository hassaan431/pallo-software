# Role-Based Financial and Cost Data Protection

We decided to standardize all tenant operations into three fixed operational roles (`admin`, `salesman`, `warehouse_manager`) with strict backend and frontend scoping of sensitive commercial data.

## Considered Options

- **Custom Granular Permission Engine (ACL / RBAC matrix)**: Allows custom permission groups per company, but adds high database complexity and administration overhead for an early-stage SaaS.
- **Three Standardized Roles (Selected)**: Provides immediate security and separation of concerns for wholesale/distribution businesses:
  - `admin`: Complete access to financials, net margins, supplier purchase costs, settings, and staff accounts.
  - `salesman`: Point of Sale (POS) and sales entry only. Supplier costs, purchase bills, and net profit margins are strictly filtered out.
  - `warehouse_manager`: Inventory management, stock adjustments, and receiving shipments only. Customer revenue and financial ledgers are strictly filtered out.

## Consequences

- API endpoints and templates for reports (`/reports`), expenses (`/expenses`), and profit analysis must enforce `role == 'admin'`.
- Product endpoints queried by salesmen return selling prices only, masking supplier `cost_price`.
