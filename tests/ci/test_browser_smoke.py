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
            page.get_by_text("Find Customers", exact=True).first.click()
            choose_product = page.get_by_text("Choose your product", exact=True).count()
            empty_state = page.get_by_text("Start with something you sell", exact=True).count()
            assert choose_product + empty_state == 1
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
