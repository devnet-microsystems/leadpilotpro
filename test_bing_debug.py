from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    page = context.new_page()
    page.goto("https://www.bing.com/search?q=Web+Design+Agencies+London")
    page.screenshot(path="bing_debug.png", full_page=True)
    anchors = page.locator("a").evaluate_all("els => els.map(e => e.href)")
    print(f"Total links: {len(anchors)}")
    for a in anchors:
        if 'ck/a' in a:
            print("Found ck/a link:", a)
    browser.close()
