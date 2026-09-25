# 📘 AK Distributors — Help Center & Software Manual

Welcome to the **AK Distributors Inventory and Invoice Management System**. This comprehensive guide is designed to help you and your team navigate the software, manage your daily operations, and streamline your business workflows. 

---

## 📑 Table of Contents

1. [General Workflows (Step-by-Step)](#general-workflows)
   - [📦 Introducing a New Product or Brand](#1-introducing-a-new-product-or-brand)
   - [📥 Receiving New Inventory (Purchases)](#2-receiving-new-inventory-purchases)
   - [🧾 Recording a Sale & Invoicing](#3-recording-a-sale--invoicing)
   - [🚚 Transferring Stock Between Warehouses](#4-transferring-stock-between-warehouses)
2. [Module Guide (Navigation)](#module-guide)
   - [📊 Dashboards & Reporting](#dashboards--reporting)
   - [📦 Products (Inventory & Purchases)](#products-inventory--purchases)
   - [🏢 Suppliers & Brands](#suppliers--brands)
   - [👥 Sales & Customers](#sales--customers)
   - [⚙️ Administration & Settings](#administration--settings)

---

## General Workflows

### 1. Introducing a New Product or Brand 📦
Before a new product can be added to your catalogue or received in a shipment, the system needs to recognize the **Supplier/Brand**.

**Step 1: Register the Supplier/Brand**
*Navigate to:* **[Suppliers & Brands](/suppliers)**
1. Click the **[Add Supplier/Brand](/suppliers)** button.
2. Fill in the required details: Supplier Name, Primary Contact Information, and the Brand Name they provide.
3. **Save** the entry. This links the brand to your supplier permanently.

**Step 2: Add the Product to the Catalogue**
*Navigate to:* **[Inventory](/inventory)**
1. Click the **[Add New Product](/inventory)** button.
2. Complete the product profile: 
   - **Name & Description:** Make this clear for your POS and Invoices.
   - **Category & Brand:** Select the Brand you just created in Step 1.
   - **Pricing:** Set your *Cost Price* (what you pay) and *Selling Price* (what the customer pays).
3. **Save** the product. 
*Note: The product is now in your system, but it will have **0 stock** until you record a purchase shipment.*

### 2. Receiving New Inventory (Purchases) 📥
When a physical shipment of goods arrives at your warehouse, you must record it as a **Purchase**. This process increases your on-hand stock and updates your Cost of Goods accurately.

**Step 1: Log the Incoming Shipment**
*Navigate to:* **[Purchases](/purchases)**
1. Click **[New Purchase](/purchases)** to open the receiving form.
2. Select the **Supplier** providing the goods.
3. Choose the **Destination Warehouse** where the goods are being unloaded.
4. **Add Items:** Search for the products received, and input the exact quantities and unit costs.
5. **Additional Costs:** Add any freight, tax, or shipping fees to ensure your profit margins are calculated accurately later.
6. **Submit** the purchase. 

*Result:* The stock quantities for those items in the selected warehouse will instantly increase, making them available for sale.

### 3. Recording a Sale & Invoicing 🧾
Recording a sale deducts from your active inventory, calculates your profit margins, and generates a professional invoice for the client.

**Step 1: Create the Customer Profile (Optional but Recommended)**
*Navigate to:* **[Customers](/customers)**
* If the customer is new, click **[Add Customer](/customers)** to input their Name, Phone, and Address. 
* If they are a returning customer, proceed directly to Step 2.

**Step 2: Process the Sale**
*Navigate to:* **[Sales](/sales)**
1. Click **[Record Sale](/sales)**.
2. Select the **Customer** from the dropdown list.
3. Select the **Dispatching Warehouse** (where the goods will be taken from).
4. **Build the Cart:** Add products, adjust quantities, and set the final selling price. *You can offer line-item discounts directly here.*
5. **Totals & Fees:** Add any applicable Taxes or Delivery Fees.
6. **Payment Status:** Mark the invoice as **Paid**, **Partial**, or **Unpaid**. If partial, enter the amount received.
7. **Submit** the sale.

*Result:* The system deducts the stock, logs the revenue, and provides a button to **Generate PDF Invoice** which you can print or email.

### 4. Transferring Stock Between Warehouses 🚚
If you operate multiple storage locations or storefronts, you will frequently need to move inventory between them to balance stock levels.

*Navigate to:* **[Transfers](/inventory_transfers)** *(or via Inventory -> Transfers)*
1. Click **[New Transfer](/inventory_transfers)**.
2. Select the **Source Warehouse** (where the goods are currently stored).
3. Select the **Destination Warehouse** (where the goods are going).
4. Add the specific products and the exact quantities being moved.
5. **Confirm** the transfer.

*Result:* Stock is immediately deducted from the source and added to the destination. Your total company inventory remains unchanged.

---

## Module Guide

### Dashboards & Reporting 📊
- **[Dashboard](/dashboard):** Your financial command center. View live snapshots of Daily and Monthly Sales, Gross Profit, and Net Profit. It highlights recent sales and flags upcoming/overdue payments. Look for the **[Walkaround Tour](/dashboard)** button here if you need a visual refresher!
- **[Reports](/reports):** The analytical engine. Generate highly detailed financial and performance reports over custom date ranges. Crucial for end-of-month accounting.

### Products (Inventory & Purchases) 📦
- **[Inventory](/inventory):** The master list of all products. View real-time stock levels across different warehouses, adjust pricing, and track historical stock movements for specific items.
- **[Purchases (Shipments)](/purchases):** The logbook of historical shipments and incoming stock. 
- **[Transfers](/inventory_transfers):** A complete audit trail of all internal stock movements between your warehouses.

### Suppliers & Brands 🏢
- **[Suppliers & Brands](/suppliers):** A CRM for your vendors. Keep track of the companies you purchase goods from and the specific brands they supply.
- **[Warehouses](/warehouses):** Manage your physical storage network. You can add new locations (e.g., "Main Distribution Center", "Downtown Retail Store") here.

### Sales & Customers 👥
- **[Sales](/sales):** The master ledger of all transactions. You can view past invoices, track down unpaid accounts, and log payments against existing debts.
- **[Customers](/customers):** Your client directory. Track customer contact details, outstanding balances, and view their lifetime purchase history.

### Administration & Settings ⚙️
- **[Expenses](/expenses):** Log operational business expenses (rent, utilities, payroll) here. *This data is essential for the Dashboard to accurately calculate your true Net Profit.*
- **[Users](/users):** Manage your staff's access. Add employees and assign roles (e.g., Admin vs. Standard User) to protect sensitive financial data.
- **[Brochure Settings](/brochure_settings):** Control the content, branding, and visibility of your public-facing product catalogue website.
- **[POS Catalogue](/pos):** Opens the streamlined Point-of-Sale interface designed for rapid, over-the-counter transactions.

---
*Powered by AK Distributors Software Architecture.*
