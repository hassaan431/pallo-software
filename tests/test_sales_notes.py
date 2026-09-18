import pytest
import time
from playwright.sync_api import Page, expect

def test_sales_notes_optional_field(page: Page):
    # Log in
    page.goto("http://localhost:5000/login")
    page.fill("input[name='username']", "admin")
    page.fill("input[name='password']", "admin123")
    page.click("button[type='submit']")
    expect(page).to_have_url("http://localhost:5000/dashboard")

    # Go to New Sale (which is just /sales)
    page.on("dialog", lambda dialog: print(f"DIALOG: {dialog.message}") or dialog.accept())
    page.goto("http://localhost:5000/sales")
    expect(page.locator("h1").first).to_contain_text("Sales")

    # Pick a customer using evaluate to bypass autocomplete UI flakiness
    page.evaluate("document.getElementById('customerId').value = '1'")
    page.evaluate("document.getElementById('customerSearch').value = 'Quotation'")

    # Click 'Add Item'
    page.click("button#addItemBtn")

    # Fill in product description and set a fake product_id so it isn't skipped by the form validator
    row = page.locator("tr.line-item-row").last
    row.locator(".description-input").fill("Test Product for Notes")
    page.evaluate("document.querySelectorAll('tr.line-item-row')[1].dataset.productId = '-1'")

    # Fill the notes field
    row.locator(".item-notes-input").fill("2 CT Special")

    # Give a rate and qty
    row.locator(".qty-input").fill("1")
    row.locator(".rate-input").fill("10.50")

    # Save the sale
    with page.expect_navigation():
        page.click("button#saveSaleBtn")

    expect(page.locator("h1").first).to_contain_text("Sales")

    # Click 'Edit' on the most recent sale
    edit_href = page.evaluate("document.evaluate(\"//button[text()='Edit']/..\", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.href")
    page.goto(edit_href)

    # Wait for the edit page to load (goto handles this)
    # page.wait_for_url(f"http://localhost:5000{edit_href}")

    # Check if the notes field still has "2 CT Special"
    saved_note = page.locator("tr.line-item-row").first.locator(".item-notes-input").input_value()
    assert saved_note == "2 CT Special", f"Expected notes to be '2 CT Special', got '{saved_note}'"

    # Also verify it prints in the PDF by generating it
    # We can't easily parse PDF in Playwright, but we can verify the API route doesn't crash
    pdf_href = page.evaluate("document.querySelector('a.btn-pdf').href")
    
    with page.expect_response(lambda response: response.url.endswith(pdf_href) and response.status == 200) as response_info:
        # Navigate to the PDF route to trigger it
        page.goto(pdf_href)

    response = response_info.value
    assert response.headers["content-type"] == "application/pdf"
