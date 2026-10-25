# Pallo ERP & SaaS

Pallo is a multi-tenant business management and inventory system enabling wholesale, distribution, and retail companies to track stock across warehouses, manage purchases and sales, generate invoices, and handle customer balances.

## Language

**Company**:
An independent business organization registered on Pallo with isolated data, branding, warehouses, and users.
_Avoid_: Workspace, organization, account, client

**SuperAdmin**:
A platform administrator with global oversight across all registered Companies, metrics, and account statuses.
_Avoid_: System admin, root, owner

**User**:
An authenticated individual associated with a Company (or platform SuperAdmin) holding a specific operational role (`superadmin`, `admin`, `salesman`, `warehouse_manager`).
_Avoid_: Member, employee, profile

**Company Slug**:
A URL-safe unique identifier for a Company used in public catalogue links and API routing (e.g., `ak-distributors`).
_Avoid_: Subdomain, handle, username

**Customer**:
A person or business that purchases products from a Company and has an accounts receivable balance.
_Avoid_: Client, buyer, debtor

**Product**:
A distinct physical good tracked in inventory, categorized, priced, and sold by a Company.
_Avoid_: Item, SKU, article

**Warehouse**:
A physical storage location belonging to a Company holding product inventory and serving as source/destination for transfers.
_Avoid_: Branch, depot, store, facility

**Sale**:
A finalized or credit commercial transaction issuing an Invoice to a Customer and deducting warehouse inventory.
_Avoid_: Order, deal, checkout

**Invoice**:
The legal payment document and PDF issued to a Customer for a Sale, carrying sequential numbering scoped to the Company.
_Avoid_: Bill, receipt, statement

**Purchase**:
A recorded inbound shipment of products received from a Supplier into a specific Warehouse.
_Avoid_: Restock, procurement, order

**Supplier**:
An external vendor providing goods and raw inventory to a Company.
_Avoid_: Vendor, manufacturer, distributor

**Stock Transfer**:
An internal movement of product inventory from a source Warehouse to a destination Warehouse within the same Company.
_Avoid_: Movement, transit, relocation
