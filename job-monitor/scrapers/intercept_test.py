"""Network intercept diagnostic - find API endpoints for SPA career sites."""
from playwright.sync_api import sync_playwright
import json

URL = "https://careers.airbnb.com/positions/"


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        api_calls = []

        def handle_response(response):
            url = response.url
            content_type = response.headers.get('content-type', '')
            if 'json' in content_type and any(kw in url.lower() for kw in ['job', 'position', 'career', 'opening', 'requisition']):
                try:
                    body = response.json()
                    api_calls.append({
                        'url': url,
                        'status': response.status,
                        'body_keys': list(body.keys()) if isinstance(body, dict) else f"list[{len(body)}]",
                        'sample': str(body)[:500]
                    })
                except Exception:
                    pass

        page.on('response', handle_response)
        page.goto(URL, timeout=60000, wait_until='networkidle')
        page.wait_for_timeout(5000)

        print(f"\nFound {len(api_calls)} matching API calls:\n")
        for call in api_calls:
            print(f"URL: {call['url']}")
            print(f"Status: {call['status']}")
            print(f"Keys: {call['body_keys']}")
            print(f"Sample: {call['sample']}")
            print("---")

        browser.close()


if __name__ == '__main__':
    run()

