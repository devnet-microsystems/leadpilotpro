from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    page = context.new_page()
    page.goto("https://www.bing.com/search?q=Top+Web+Agencies+London&cc=GB")
    anchors = page.locator("li.b_algo h2 a").evaluate_all("els => els.map(e => e.href)")
    for a in anchors:
        print(a)
    browser.close()
