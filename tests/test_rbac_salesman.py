import pytest
from playwright.sync_api import Page, expect

def test_salesman_rbac(page: Page):
    # Log in as zain (warehouse 2 salesman)
    page.goto("http://localhost:5000/login")
    page.fill("input[name='username']", "zain")
    page.fill("input[name='password']", "testpass")
    page.click("button[type='submit']")
    
    # Should redirect to pos
    expect(page).to_have_url("http://localhost:5000/pos")
    
    # Wait for product grid to populate
    page.wait_for_selector(".product-card")
    
    # Click the first product to add to cart so checkout button enables
    page.locator(".product-card").first.click()
    
    # Click checkout
    page.click("#checkoutBtn")
    
    # Wait for modal
    page.wait_for_selector("#checkoutModal", state="visible")
    
    # Type 'Customer' into the customer search input
    page.fill("#customerSearchInput", "Customer")
    
    # Wait for autocomplete dropdown to show
    page.wait_for_selector("#customerDropdown .autocomplete-item")
    
    # Assert that Zain's customer is visible
    expect(page.locator("#customerDropdown")).to_contain_text("Customer For Zain")
    
    # Assert that Salesman1's customer is NOT visible
    expect(page.locator("#customerDropdown")).not_to_contain_text("Customer For Salesman1")
