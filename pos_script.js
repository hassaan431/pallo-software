    let products = [];
    let brands = new Set();
    let cart = {}; // product_id -> qty
    let cartVariants = {}; // product_id -> variant string
    
    // Load saved cart from localStorage if available
    try {
      const savedCart = localStorage.getItem('pos_cart');
      const savedVariants = localStorage.getItem('pos_cartVariants');
      if (savedCart) cart = JSON.parse(savedCart);
      if (savedVariants) cartVariants = JSON.parse(savedVariants);
    } catch (e) {
      console.error("Failed to load cart from localStorage", e);
    }

    let customers = [];
    let selectedCustomerId = null;

    const productGrid = document.getElementById('productGrid');
    const categoryTabs = document.getElementById('categoryTabs');
    const searchInput = document.getElementById('searchInput');
    const cartItemsDiv = document.getElementById('cartItems');
    const cartTotalSpan = document.getElementById('cartTotal');
    const checkoutBtn = document.getElementById('checkoutBtn');
    
    // Format money
    const money = (val) => {
      const v = Number(val || 0);
      if (Math.abs(v - Math.round(v * 100) / 100) < 0.00001) {
        return '$' + v.toFixed(2);
      }
      return '$' + v.toFixed(4);
    };

    // Initialize
    async function loadProducts() {
      try {
        const prodRes = await fetch(`/products/list?warehouse_id=${document.getElementById("warehouseSelect") ? document.getElementById("warehouseSelect").value : ""}`).then(r => r.json());
        products = prodRes;
        renderProducts(products);
      } catch (e) { console.error(e); }
    }

    async function init() {
      try {
        const [prodRes, custRes] = await Promise.all([
          fetch(`/products/list?warehouse_id=${document.getElementById("warehouseSelect") ? document.getElementById("warehouseSelect").value : ""}`).then(r => r.json()),
          fetch('/customers/list').then(r => r.json())
        ]);
        products = prodRes;
        if(custRes) {
          customers = custRes;
        }
        
        products.forEach(p => {
          if(p.brand_name) brands.add(p.brand_name);
        });
        
        renderBrands();
        renderProducts();
        renderCart(); // Render cart after products are loaded
      } catch (e) {
        console.error("Failed to load POS data", e);
      }
    }

    function renderBrands() {
      categoryTabs.innerHTML = '<button class="category-btn active" data-id="all">All Products</button>';
      Array.from(brands).sort().forEach(brand => {
        const btn = document.createElement('button');
        btn.className = 'category-btn';
        btn.dataset.id = brand;
        btn.textContent = brand;
        btn.onclick = () => {
          document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          renderProducts(brand, searchInput.value);
        };
        categoryTabs.appendChild(btn);
      });
      categoryTabs.querySelector('[data-id="all"]').onclick = (e) => {
        document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        renderProducts('all', searchInput.value);
      };
    }

    function renderProducts(brandFilter = 'all', searchFilter = '') {
      productGrid.innerHTML = '';
      let filtered = products.filter(p => p.stock_quantity > 0);
      if(brandFilter !== 'all') {
        filtered = filtered.filter(p => p.brand_name === brandFilter);
      }
      if(searchFilter) {
        const lower = searchFilter.toLowerCase();
        filtered = filtered.filter(p => p.name.toLowerCase().includes(lower) || (p.brand_name && p.brand_name.toLowerCase().includes(lower)));
      }

      filtered.forEach(p => {
        const card = document.createElement('div');
        card.className = 'product-card';
        card.onclick = () => addToCart(p.id);
        let imageHtml = '';
        if (p.image_url) {
          imageHtml = `<img src="${p.image_url}" class="product-image" alt="Img">`;
        } else {
          imageHtml = `<div class="product-image" style="display:flex; align-items:center; justify-content:center; background:var(--card-bg, #fff); color:var(--text, #333); font-size:0.9rem; font-weight:bold; text-align:center; padding:10px; line-height:1.2;">${p.name}</div>`;
        }
        
        let stockClass = p.stock_quantity > 0 ? 'stock-ok' : 'stock-out';
        let stockText = p.stock_quantity > 0 ? `${p.stock_quantity} in stock` : 'Out of Stock (Warn)';
        let openBadge = p.is_open ? `<span style="background:var(--primary); color:white; font-size:0.7rem; padding:2px 6px; border-radius:4px; margin-left:0.5rem;">Open Product</span>` : '';
        
        card.innerHTML = `
          ${imageHtml}
          <div class="product-info">
            <h3 title="${p.name}">${p.name}</h3>
            <div class="brand">${p.brand_name || 'Generic'} ${openBadge}</div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top: 0.5rem;">
              <div class="price">${money(p.selling_price)}</div>
              <div class="stock ${stockClass}">${stockText}</div>
            </div>
          </div>
        `;
        productGrid.appendChild(card);
      });
    }

    searchInput.addEventListener('input', (e) => {
      const activeCat = document.querySelector('.category-btn.active').dataset.id;
      renderProducts(activeCat, e.target.value);
    });

    // Cart Logic
    function addToCart(productId) {
      const p = products.find(x => x.id == productId);
      if(!p) return;
      
      if(!cart[productId]) cart[productId] = 0;
      
      if(cart[productId] >= p.stock_quantity) {
        alert(`Cannot add more. Only ${p.stock_quantity} available in stock.`);
        return;
      }
      
      cart[productId]++;
      renderCart();
    }
    function updateQty(productId, delta) {
      if(!cart[productId]) return;
      
      const p = products.find(x => x.id == productId);
      if(!p) return;
      
      if(delta > 0 && cart[productId] + delta > p.stock_quantity) {
        alert(`Cannot add more. Only ${p.stock_quantity} available in stock.`);
        return;
      }
      
      cart[productId] += delta;
      if(cart[productId] <= 0) delete cart[productId];
      
      renderCart();
    }
    
    function setQty(productId, value) {
      const val = parseInt(value, 10);
      if (isNaN(val) || val <= 0) {
        delete cart[productId];
      } else {
        const p = products.find(x => x.id == productId);
        if (p && val > p.stock_quantity) {
          alert(`Cannot set qty to ${val}. Only ${p.stock_quantity} available in stock.`);
          cart[productId] = p.stock_quantity;
        } else {
          cart[productId] = val;
        }
      }
      renderCart();
    }
    
    function deleteCartItem(productId) {
      delete cart[productId];
      renderCart();
    }

    function setVariant(productId, val) {
      cartVariants[productId] = val.trim();
      renderCart();
    }

    document.getElementById('clearCartBtn').onclick = () => {
      if (!confirm("Are you sure you want to clear the entire cart?")) return;
      cart = {};
      cartVariants = {};
      renderCart();
    };



    function renderCart() {
      cartItemsDiv.innerHTML = '';
      let total = 0;
      let count = 0;
      for (const [pid, qty] of Object.entries(cart)) {
        const p = products.find(x => x.id == pid);
        if (!p) continue;
        const variantStr = cartVariants[pid] || '1';
        const pmMatch = variantStr.match(/[\d.]+/);
        const pm = p.is_open ? (pmMatch ? parseFloat(pmMatch[0]) : 1.0) : 1.0;
        
        const lineTotal = p.selling_price * qty * pm;
        
        total += lineTotal;
        count += qty;
        
        let variantInput = '';
        let displayUnit = p.unit && p.unit !== 'Each' ? ` (${p.unit})` : '';
        if (p.is_open) {
          variantInput = `
            <div style="margin-top: 4px; font-size: 0.8rem;">
              <label>Variant:</label>
              <input type="text" value="${variantStr}" onchange="setVariant(${pid}, this.value)" style="width: 80px; padding: 2px 4px; border: 1px solid var(--border); border-radius: 4px; font-size: 0.85rem;">
            </div>
          `;
        }
        
        const item = document.createElement('div');
        item.className = 'cart-item';
        item.innerHTML = `
          <div class="cart-item-title">${p.name}${p.is_open ? ' - ' + variantStr + displayUnit : ''} ${variantInput}</div>
          <div class="cart-item-controls">
            <span style="font-weight:600; color:var(--primary);">${money(lineTotal)}</span>
            <div style="display:flex; align-items:center; gap:0.5rem;">
              <button class="qty-btn" onclick="updateQty(${pid}, -1)">-</button>
              <input type="number" value="${qty}" onchange="setQty(${pid}, this.value)" style="font-weight:bold; width:50px; text-align:center; border:1px solid var(--border); border-radius:4px; padding: 4px; font-size: 1rem;">
              <button class="qty-btn" onclick="updateQty(${pid}, 1)">+</button>
              <button class="qty-btn" onclick="deleteCartItem(${pid})" style="background:var(--danger, #ef4444); color:white; border:none; border-radius:4px; width:28px; font-size:14px;" title="Remove Item">&times;</button>
            </div>
          </div>
        `;
        cartItemsDiv.appendChild(item);
      }
      cartTotalSpan.textContent = money(total);
      
      if(count > 0) {
        checkoutBtn.disabled = false;
        checkoutBtn.textContent = `Checkout (${count} items)`;
        document.getElementById('clearCartBtn').style.display = 'block';
      } else {
        checkoutBtn.disabled = true;
        checkoutBtn.textContent = 'Checkout';
        cartItemsDiv.innerHTML = '<div style="color:var(--text-muted); text-align:center; padding-top:2rem;">Cart is empty</div>';
        document.getElementById('clearCartBtn').style.display = 'none';
      }
      
      // Save state to local storage
      try {
        localStorage.setItem('pos_cart', JSON.stringify(cart));
        localStorage.setItem('pos_cartVariants', JSON.stringify(cartVariants));
      } catch (e) {
        console.error("Failed to save cart to localStorage", e);
      }
    }

    // Checkout Modal Logic
    const checkoutModal = document.getElementById('checkoutModal');
    const customerSearchContainer = document.getElementById('customerSearchContainer');
    const customerSearchInput = document.getElementById('customerSearchInput');
    const customerDropdown = document.getElementById('customerDropdown');
    const selectedCustomerContainer = document.getElementById('selectedCustomerContainer');
    const selectedCustomerName = document.getElementById('selectedCustomerName');
    
    const newCustFields = document.getElementById('newCustomerFields');
    const paymentType = document.getElementById('paymentType');
    const amountPaidGroup = document.getElementById('amountPaidGroup');
    const errorDiv = document.getElementById('checkoutError');

    checkoutBtn.onclick = () => {
      errorDiv.style.display = 'none';
      checkoutModal.style.display = 'flex';
      paymentType.value = 'cash';
      amountPaidGroup.classList.add('hidden');
      if (document.getElementById('dueDateGroup')) {
        document.getElementById('dueDateGroup').classList.add('hidden');
      }
      resetCustomerSelection();
    };

    document.getElementById('closeCheckout').onclick = () => checkoutModal.style.display = 'none';
    document.getElementById('cancelCheckout').onclick = () => checkoutModal.style.display = 'none';

    function resetCustomerSelection() {
      selectedCustomerId = null;
      customerSearchInput.value = '';
      customerSearchContainer.style.display = 'flex';
      selectedCustomerContainer.style.display = 'none';
      newCustFields.style.display = 'none';
      customerDropdown.classList.add('hidden');
    }

    document.getElementById('changeCustomerBtn').onclick = resetCustomerSelection;

    // Autocomplete Logic
    function showCustomerDropdown(filter = '') {
      customerDropdown.innerHTML = '';
      customerDropdown.classList.remove('hidden');
      
      const filtered = customers.filter(c => c.name.toLowerCase().includes(filter.toLowerCase()));
      
      filtered.forEach(c => {
        const div = document.createElement('div');
        div.className = 'autocomplete-item';
        div.textContent = c.name;
        div.onmousedown = (e) => { // mousedown fires before blur
          e.preventDefault();
          selectCustomer(c.id, c.name);
        };
        customerDropdown.appendChild(div);
      });
      
      const addNew = document.createElement('div');
      addNew.className = 'autocomplete-item add-new';
      addNew.textContent = "+ Add New Customer";
      addNew.onmousedown = (e) => {
        e.preventDefault();
        selectNewCustomer(customerSearchInput.value);
      };
      customerDropdown.appendChild(addNew);
    }

    customerSearchInput.addEventListener('focus', () => showCustomerDropdown(customerSearchInput.value));
    customerSearchInput.addEventListener('input', (e) => showCustomerDropdown(e.target.value));
    customerSearchInput.addEventListener('blur', () => {
      setTimeout(() => customerDropdown.classList.add('hidden'), 150);
    });

    function selectCustomer(id, name) {
      selectedCustomerId = id;
      customerSearchContainer.style.display = 'none';
      selectedCustomerContainer.style.display = 'flex';
      selectedCustomerName.textContent = name;
      newCustFields.style.display = 'none';
      customerDropdown.classList.add('hidden');
    }

    function selectNewCustomer(typedName) {
      selectedCustomerId = null;
      customerSearchContainer.style.display = 'none';
      selectedCustomerContainer.style.display = 'flex';
      selectedCustomerName.textContent = "New Customer";
      newCustFields.style.display = 'flex';
      customerDropdown.classList.add('hidden');
      
      // Auto fill the name field with what they typed in search
      document.getElementById('custName').value = typedName;
      document.getElementById('custName').focus();
    }

    paymentType.onchange = (e) => {
      if(e.target.value === 'credit') {
        amountPaidGroup.classList.remove('hidden');
        document.getElementById('dueDateGroup').classList.remove('hidden');
      } else {
        amountPaidGroup.classList.add('hidden');
        document.getElementById('dueDateGroup').classList.add('hidden');
        if (e.target.value === 'cash') {
          document.getElementById('custTerms').value = '';
        }
      }
    };

    document.getElementById('submitOrderBtn').onclick = async () => {
      errorDiv.style.display = 'none';
      
      const payload = {
        customer_id: selectedCustomerId,
        customer_name: document.getElementById('custName').value,
        customer_phone: document.getElementById('custPhone').value,
        customer_area: document.getElementById('custArea').value,
        customer_bill: document.getElementById('custBillAddress').value,
        customer_ship: document.getElementById('custShipAddress').value,
        customer_state: document.getElementById('custState').value,
        customer_email: document.getElementById('custEmail').value,
        customer_terms: (paymentType.value === 'cash') ? '' : document.getElementById('custTerms').value,
        payment_type: paymentType.value,
        amount_paid: document.getElementById('amountPaid').value || 0,
        due_date: document.getElementById('custDueDate').value,
        warehouse_id: document.getElementById('warehouseSelect') ? document.getElementById('warehouseSelect').value : null,
        items: Object.entries(cart).map(([id, qty]) => {
          const p = products.find(x => x.id == id);
          if (p && p.is_open) {
            const variantStr = cartVariants[id] || '1';
            const pmMatch = variantStr.match(/[\d.]+/);
            const pm = pmMatch ? parseFloat(pmMatch[0]) : 1.0;
            let displayUnit = p.unit && p.unit !== 'Each' ? ` (${p.unit})` : '';
            return {
              id: id,
              qty: qty,
              description: p.name + ' - ' + variantStr + displayUnit,
              packing_multiplier: pm
            };
          }
          return { id, qty };
        })
      };
      
      if(selectedCustomerContainer.style.display === 'none') {
        errorDiv.textContent = 'Please select or add a customer.';
        errorDiv.style.display = 'block';
        return;
      }

      if(!payload.customer_id) {
         if (!payload.customer_name || !document.getElementById('custPhone').value || !document.getElementById('custBillAddress').value) {
            errorDiv.textContent = 'For new customers, Full Name, Phone, and Billing Address are mandatory.';
            errorDiv.style.display = 'block';
            return;
         }
      }
      
      document.getElementById('submitOrderBtn').disabled = true;
      document.getElementById('submitOrderBtn').textContent = 'Processing...';

      try {
        const res = await fetch('/pos/submit_order', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if(res.ok && data.ok) {
          window.open(`/sales/${data.sale_id}/invoice/pdf`, '_blank');
          cart = {};
          cartVariants = {};
          renderCart();
          init(); // Refresh products to update stock
          checkoutModal.style.display = 'none';
        } else {
          errorDiv.textContent = data.error || 'Failed to submit order.';
          errorDiv.style.display = 'block';
        }
      } catch (err) {
        errorDiv.textContent = 'Network error occurred.';
        errorDiv.style.display = 'block';
      }
      
      document.getElementById('submitOrderBtn').disabled = false;
      document.getElementById('submitOrderBtn').textContent = 'Place Order';
    };

    // Run
    init();
