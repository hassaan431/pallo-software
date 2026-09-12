import pytest
from playwright.sync_api import Page, expect

def test_login_and_dashboard(page: Page):
    # Navigate to the app
    page.goto("http://localhost:5000/login")
    
    # Fill out the login form
    page.fill("input[name='username']", "admin")
    page.fill("input[name='password']", "admin123")
    
    # Submit the login form
    page.click("button[type='submit']")
    
    # Verify redirection to dashboard
    expect(page).to_have_url("http://localhost:5000/dashboard")
    
    # Verify the page title/header
    expect(page.locator("h1").first).to_contain_text("Dashboard")
