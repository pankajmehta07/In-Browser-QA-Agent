import os
from playwright.sync_api import sync_playwright

url = os.getenv("TARGET_APP_URL", "http://target-app:5173")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    try:
        response = page.goto(url, wait_until="domcontentloaded")

        print(f"URL: {page.url}")
        print(f"Status: {response.status if response else 'No response'}")
        print(f"Title: {page.title()}")

    finally:
        browser.close()