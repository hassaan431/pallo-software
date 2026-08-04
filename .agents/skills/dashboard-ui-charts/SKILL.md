---
name: dashboard-ui-charts
description: Guidelines, reusable patterns, styling rules, and charting standards for building modern business dashboards, interactive data tables, KPI metric cards, Chart.js integrations, modals, and responsive UI components in Flask/Jinja2 applications.
---

# Dashboard UI & Charting Guidelines (`dashboard-ui-charts`)

This skill provides best practices, CSS design tokens, and JavaScript code patterns for building premium, responsive, and data-dense business dashboards in web applications.

---

## 1. Visual Aesthetics & Design System Tokens

### Color Palette (Business & Financial)
- **Primary / Brand**: `#10b981` (Emerald Green - Sales/Revenue)
- **Primary Hover**: `#059669`
- **Secondary / Accent**: `#3b82f6` (Royal Blue - Information / Secondary KPIs)
- **Warning / Pending**: `#f59e0b` (Amber - Overdue / Low Stock)
- **Danger / Negative**: `#ef4444` (Crimson - Out of Stock / Unpaid)
- **Background Main**: `#f8fafc` (Off-white / Slate 50)
- **Card Background**: `#ffffff`
- **Text Main**: `#0f172a` (Slate 900)
- **Text Muted**: `#64748b` (Slate 500)
- **Borders & Dividers**: `#e2e8f0` (Slate 200)

### Card & Elevation System
- **Default Card Shadow**: `0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)`
- **Hover Elevation**: `0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)`
- **Border Radius**: `12px` for main container cards, `8px` for buttons & inputs.

---

## 2. KPI Metric Cards Pattern

KPI cards should display clear monetary values, labels, and trend context.

```html
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-header">
      <span class="kpi-title">DAILY SALE AMOUNT</span>
      <div class="kpi-icon-wrapper green">
        <i class="fas fa-dollar-sign"></i>
      </div>
    </div>
    <div class="kpi-value">${{ "%.2f"|format(daily_revenue) }}</div>
    <div class="kpi-subtitle">
      <span class="kpi-trend positive"><i class="fas fa-arrow-up"></i> Today's Total</span>
    </div>
  </div>
</div>
```

```css
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.25rem;
  margin-bottom: 2rem;
}

.kpi-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.kpi-title {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.kpi-value {
  font-size: 1.75rem;
  font-weight: 800;
  color: #0f172a;
  margin: 0.5rem 0;
}
```

---

## 3. Chart.js Standards & Best Practices

### Line Chart (Daily / Monthly Sales Trend)
Always enable responsiveness, smooth tension curves, area gradients, and custom currency tooltips.

```javascript
// Initialize Chart.js Line Chart with Gradient Fill
function initSalesChart(canvasId, labels, dataPoints) {
  const ctx = document.getElementById(canvasId).getContext('2d');
  
  const gradient = ctx.createLinearGradient(0, 0, 0, 300);
  gradient.addColorStop(0, 'rgba(16, 185, 129, 0.25)');
  gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Sales ($)',
        data: dataPoints,
        borderColor: '#10b981',
        borderWidth: 3,
        backgroundColor: gradient,
        fill: true,
        tension: 0.35,
        pointBackgroundColor: '#10b981',
        pointHoverRadius: 6,
        pointRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          mode: 'index',
          intersect: false,
          callbacks: {
            label: function(context) {
              let value = context.parsed.y || 0;
              return 'Sales: $' + value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
            }
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#64748b', font: { family: 'Inter, sans-serif', size: 11 } }
        },
        y: {
          grid: { color: '#f1f5f9' },
          ticks: {
            color: '#64748b',
            font: { family: 'Inter, sans-serif', size: 11 },
            callback: function(value) { return '$' + value; }
          },
          beginAtZero: true
        }
      }
    }
  });
}
```

---

## 4. Status Badges & Data Tables

Use semantic colors for invoice & inventory statuses:

```html
<!-- Status Badges -->
<span class="badge badge-success">Paid</span>
<span class="badge badge-warning">Partial</span>
<span class="badge badge-danger">Overdue</span>
```

```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.625rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: capitalize;
}

.badge-success { background-color: #d1fae5; color: #065f46; }
.badge-warning { background-color: #fef3c7; color: #92400e; }
.badge-danger  { background-color: #fee2e2; color: #991b1b; }
.badge-info    { background-color: #dbeafe; color: #1e40af; }
```

---

## 5. Modal Dialog Best Practices

1. **Accessibility**: Always include `role="dialog"` and `aria-modal="true"`.
2. **Keyboard Navigation**: Close on `Esc` key press.
3. **Backdrop Blur**: Use `backdrop-filter: blur(4px)` for a modern glass effect.
4. **Transition**: Fade and slide scale up smoothly (`transform: scale(0.95)` -> `scale(1.0)`).

```css
.modal-backdrop {
  position: fixed;
  inset: 0;
  background-color: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease-in-out;
}

.modal-backdrop.active {
  opacity: 1;
  pointer-events: auto;
}

.modal-content {
  background: #ffffff;
  border-radius: 12px;
  width: 90%;
  max-width: 600px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  transform: scale(0.95);
  transition: transform 0.2s ease-in-out;
}

.modal-backdrop.active .modal-content {
  transform: scale(1);
}
```

---

## 6. Implementation Checklist for New Dashboard Pages
- [ ] Add loading skeletons / spinners for async dynamic data loads.
- [ ] Format all monetary values to 2 decimal places with currency symbols (`$`).
- [ ] Ensure full responsiveness on mobile screens (< 768px).
- [ ] Double-check Chart.js canvas elements are wrapped in a container with explicit height (e.g. `height: 320px; position: relative`).
