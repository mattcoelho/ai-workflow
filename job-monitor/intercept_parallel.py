"""Intercept network requests to find Parallel ATS API auth headers."""
from playwright.sync_api import sync_playwright

URL = "https://www.useparallel.com/table22/careers"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        captured = []

        def handle_request(request):
            if "useparallel.com" in request.url and "find-jobs" in request.url:
                print(f"\n[CAPTURED] {request.url}")
                print(f"[HEADERS] {dict(request.headers)}")
                captured.append({"url": request.url, "headers": dict(request.headers)})

        page.on("request", handle_request)
        page.goto(URL, wait_until="networkidle", timeout=30000)

        if not captured:
            print("[WARN] No find-jobs requests captured. Trying to wait longer...")
            page.wait_for_timeout(5000)

        browser.close()

        if not captured:
            print("[FAIL] No API requests captured at all.")
        else:
            print(f"\n[DONE] Captured {len(captured)} requests.")

run()
