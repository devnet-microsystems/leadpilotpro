from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    page = context.new_page()
    res = page.goto("https://www.bing.com/search?q=Top+Web+Agencies+London")
    print("Status:", res.status)
    print("Blocked?", "captcha" in page.content().lower() or "verify" in page.content().lower())
    browser.close()
