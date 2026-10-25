-- ========================================================
-- Pallo Multi-Tenant SaaS - PostgreSQL DDL Schema
-- ========================================================

-- Master Tenant Table: Companies
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    currency TEXT DEFAULT '$',
    invoice_prefix TEXT DEFAULT 'INV-',
    starting_invoice_number INTEGER DEFAULT 1,
    bill_address TEXT,
    ship_address TEXT,
    phone TEXT,
    email TEXT,
    tax_id TEXT,
    logo_url TEXT,
    max_warehouses INTEGER DEFAULT 5,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Users (Global identity per ADR 0002)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'admin',
    is_active BOOLEAN DEFAULT TRUE,
    warehouse_id INTEGER,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Categories (Scoped per tenant)
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    CONSTRAINT uq_categories_company_name UNIQUE(company_id, name)
);

-- Brands (Scoped per tenant)
CREATE TABLE IF NOT EXISTS brands (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    commission_rate NUMERIC(6, 4) DEFAULT 0,
    show_on_website BOOLEAN DEFAULT TRUE,
    show_in_brochure BOOLEAN DEFAULT TRUE,
    CONSTRAINT uq_brands_company_name UNIQUE(company_id, name)
);

-- Warehouses (Scoped per tenant)
CREATE TABLE IF NOT EXISTS warehouses (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    location TEXT,
    commission_rate NUMERIC(6, 4) DEFAULT 0,
    commission_applies INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_warehouses_company_name UNIQUE(company_id, name)
);

-- Suppliers (Scoped per tenant)
CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    contact_name TEXT,
    phone TEXT,
    address TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Customers (Scoped per tenant)
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    bill_address TEXT,
    ship_address TEXT,
    area TEXT,
    state TEXT,
    phone TEXT,
    email TEXT,
    terms TEXT DEFAULT 'Due on Receipt',
    salesman_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Products (Scoped per tenant with exact NUMERIC precision)
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    brand TEXT,
    unit TEXT DEFAULT 'Each',
    cost_price NUMERIC(14, 4) DEFAULT 0,
    selling_price NUMERIC(14, 4) DEFAULT 0,
    stock_quantity NUMERIC(14, 4) DEFAULT 0,
    image_url TEXT,
    is_public INTEGER DEFAULT 1,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    is_open INTEGER DEFAULT 0,
    show_in_brochure INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Product Variants (Scoped per tenant)
CREATE TABLE IF NOT EXISTS product_variants (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    size TEXT,
    flavor TEXT,
    price_adjustment NUMERIC(14, 4) DEFAULT 0
);

-- Warehouse Inventory (Scoped per tenant & warehouse)
CREATE TABLE IF NOT EXISTS warehouse_inventory (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    stock_quantity NUMERIC(14, 4) DEFAULT 0,
    CONSTRAINT uq_warehouse_inventory UNIQUE(warehouse_id, product_id)
);

-- Sales (Scoped per tenant, invoice_number unique per company)
CREATE TABLE IF NOT EXISTS sales (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    invoice_number TEXT NOT NULL,
    customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
    invoice_date TEXT NOT NULL,
    due_date TEXT,
    terms TEXT,
    payment_type TEXT CHECK(payment_type IN ('cash','cheque','credit')) DEFAULT 'cash',
    discount_amount NUMERIC(14, 4) DEFAULT 0,
    subtotal NUMERIC(14, 4) DEFAULT 0,
    grand_total NUMERIC(14, 4) DEFAULT 0,
    amount_paid NUMERIC(14, 4) DEFAULT 0,
    remaining_amount NUMERIC(14, 4) DEFAULT 0,
    notes TEXT,
    status TEXT DEFAULT 'unpaid',
    salesman_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE SET NULL,
    commission_rate NUMERIC(6, 4) DEFAULT 0,
    commission_amount NUMERIC(14, 4) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_sales_company_invoice UNIQUE(company_id, invoice_number)
);

-- Sale Items (Scoped per tenant)
CREATE TABLE IF NOT EXISTS sale_items (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    description TEXT,
    qty NUMERIC(14, 4) DEFAULT 1,
    rate NUMERIC(14, 4) DEFAULT 0,
    amount NUMERIC(14, 4) DEFAULT 0,
    cost_price NUMERIC(14, 4) DEFAULT 0,
    print_dual_units INTEGER DEFAULT 0,
    packing_multiplier NUMERIC(10, 4) DEFAULT 1.0,
    commission_amount NUMERIC(14, 4) DEFAULT 0,
    notes TEXT
);

-- Purchases (Scoped per tenant)
CREATE TABLE IF NOT EXISTS purchases (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    reference_number TEXT,
    purchase_date TEXT NOT NULL,
    subtotal NUMERIC(14, 4) DEFAULT 0,
    discount_amount NUMERIC(14, 4) DEFAULT 0,
    other_charges NUMERIC(14, 4) DEFAULT 0,
    grand_total NUMERIC(14, 4) DEFAULT 0,
    amount_paid NUMERIC(14, 4) DEFAULT 0,
    remaining_amount NUMERIC(14, 4) DEFAULT 0,
    status TEXT DEFAULT 'unpaid',
    notes TEXT,
    warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Purchase Items (Scoped per tenant)
CREATE TABLE IF NOT EXISTS purchase_items (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    qty NUMERIC(14, 4) DEFAULT 1,
    cost_price NUMERIC(14, 4) DEFAULT 0,
    amount NUMERIC(14, 4) DEFAULT 0
);

-- Supplier Payments (Scoped per tenant)
CREATE TABLE IF NOT EXISTS supplier_payments (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE CASCADE,
    purchase_id INTEGER REFERENCES purchases(id) ON DELETE SET NULL,
    amount NUMERIC(14, 4) NOT NULL,
    payment_date TEXT NOT NULL,
    payment_method TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Expenses (Scoped per tenant)
CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    amount NUMERIC(14, 4) NOT NULL,
    added_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Inventory Transfers (Scoped per tenant)
CREATE TABLE IF NOT EXISTS inventory_transfers (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source_warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE RESTRICT,
    destination_warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE RESTRICT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Inventory Transfer Items (Scoped per tenant)
CREATE TABLE IF NOT EXISTS inventory_transfer_items (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    transfer_id INTEGER NOT NULL REFERENCES inventory_transfers(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    quantity NUMERIC(14, 4) NOT NULL
);

-- Inventory History (Scoped per tenant)
CREATE TABLE IF NOT EXISTS inventory_history (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    transaction_type TEXT NOT NULL,
    quantity_change NUMERIC(14, 4) NOT NULL,
    previous_stock NUMERIC(14, 4) NOT NULL,
    new_stock NUMERIC(14, 4) NOT NULL,
    reference TEXT,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ========================================================
-- Composite & Multi-Tenant Performance Indices
-- ========================================================
CREATE INDEX IF NOT EXISTS idx_users_company_id ON users(company_id);
CREATE INDEX IF NOT EXISTS idx_categories_company_id ON categories(company_id);
CREATE INDEX IF NOT EXISTS idx_brands_company_id ON brands(company_id);
CREATE INDEX IF NOT EXISTS idx_customers_company_id ON customers(company_id);
CREATE INDEX IF NOT EXISTS idx_warehouses_company_id ON warehouses(company_id);
CREATE INDEX IF NOT EXISTS idx_suppliers_company_id ON suppliers(company_id);
CREATE INDEX IF NOT EXISTS idx_products_company_id ON products(company_id);
CREATE INDEX IF NOT EXISTS idx_products_company_cat ON products(company_id, category_id);
CREATE INDEX IF NOT EXISTS idx_products_company_pub ON products(company_id, is_public);
CREATE INDEX IF NOT EXISTS idx_product_variants_comp_prod ON product_variants(company_id, product_id);
CREATE INDEX IF NOT EXISTS idx_wh_inventory_comp_wh ON warehouse_inventory(company_id, warehouse_id, product_id);
CREATE INDEX IF NOT EXISTS idx_sales_company_inv ON sales(company_id, invoice_number);
CREATE INDEX IF NOT EXISTS idx_sales_company_date ON sales(company_id, invoice_date);
CREATE INDEX IF NOT EXISTS idx_sales_company_status ON sales(company_id, status);
CREATE INDEX IF NOT EXISTS idx_sales_company_cust ON sales(company_id, customer_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_comp_sale ON sale_items(company_id, sale_id);
CREATE INDEX IF NOT EXISTS idx_purchases_company_id ON purchases(company_id);
CREATE INDEX IF NOT EXISTS idx_purchases_comp_supp ON purchases(company_id, supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchase_items_comp_purch ON purchase_items(company_id, purchase_id);
CREATE INDEX IF NOT EXISTS idx_supp_payments_comp_supp ON supplier_payments(company_id, supplier_id);
CREATE INDEX IF NOT EXISTS idx_expenses_comp_date ON expenses(company_id, date);
CREATE INDEX IF NOT EXISTS idx_transfers_company ON inventory_transfers(company_id);
CREATE INDEX IF NOT EXISTS idx_transfer_items_comp_tr ON inventory_transfer_items(company_id, transfer_id);
CREATE INDEX IF NOT EXISTS idx_inv_hist_comp_prod ON inventory_history(company_id, product_id);
CREATE INDEX IF NOT EXISTS idx_inv_hist_comp_date ON inventory_history(company_id, created_at);
