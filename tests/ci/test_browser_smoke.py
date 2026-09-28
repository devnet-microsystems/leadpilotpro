import os
import subprocess
import sys
import time

import requests
from playwright.sync_api import sync_playwright


def test_browser_smoke_local():
    env = os.environ.copy()
    env["LEADPILOT_DISABLE_AUTH"] = "1"
    port = "8765"
    base_url = f"http://127.0.0.1:{port}"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "web_server:app",
            "--host",
            "127.0.0.1",
            "--port",
            port,
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        for _ in range(60):
            try:
                r = requests.get(f"{base_url}/health", timeout=1)
                if r.ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(0.25)
        else:
            output = proc.stdout.read() if proc.stdout else ""
            raise AssertionError(f"local server did not become ready: {output[-2000:]}")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(base_url, wait_until="networkidle")
            assert "LeadPilot Pro" in page.title()
            assert page.get_by_text("Find Customers", exact=True).count() >= 1
            api = requests.get(f"{base_url}/api/products", timeout=5)
            assert api.status_code == 200, api.text
            products = api.json()
            assert isinstance(products, list)
            page.get_by_text("Find Customers", exact=True).first.click()
            page.wait_for_function(
                "() => { const el = document.getElementById('view-find'); return !!el && el.classList.contains('active') && el.textContent.trim().length > 0; }",
                timeout=5000,
            )
            find_view = page.locator("#view-find")
            assert find_view.count() == 1
            find_text = find_view.inner_text()
            assert "Find Customers" in find_text
            assert ("No ready products" in find_text) or ("Discovery budget" in find_text) or ("Ready products only." in find_text)

            page.locator("#btn-advanced").click()
            page.wait_for_function(
                "() => { const el = document.getElementById('view-advanced'); return !!el && el.classList.contains('active') && el.textContent.includes('Products') && el.textContent.includes('Diagnostics'); }",
                timeout=5000,
            )
            page.locator("#open-products").click()
            page.wait_for_function(
                "() => { const el = document.getElementById('advanced-body'); return !!el && el.textContent.includes('Product library'); }",
                timeout=5000,
            )
            page.locator("#btn-advanced").click()
            page.locator("#open-diagnostics").click()
            page.wait_for_function(
                "() => { const el = document.getElementById('advanced-body'); return !!el && el.textContent.includes('Health:'); }",
                timeout=5000,
            )
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
