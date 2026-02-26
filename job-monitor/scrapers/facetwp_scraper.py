"""FacetWP-based career site scraper (WordPress + FacetWP plugin)."""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from typing import List, Dict
from urllib.parse import urljoin


def _generate_id(url: str, title: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:50]
    path = url.rstrip('/').split('/')[-1]
    return f"{path}-{slug}"


def _parse_template(html: str, base_url: str, company_name: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, 'html.parser')
    template = soup.find(class_='facetwp-template')
    if not template:
        return []
    jobs = []
    for link in template.find_all('a', href=True):
        title = link.get_text(strip=True)
        title = re.sub(r'\s+', ' ', title).strip()
        if not title or len(title) < 5:
            continue
        href = link.get('href', '')
        job_url = urljoin(base_url, href)
        job_id = _generate_id(job_url, title)
        jobs.append({
            "id": job_id,
            "title": title,
            "location": "",
            "url": job_url,
            "company": company_name
        })
    return jobs


def scrape_facetwp(url: str, company_name: str) -> List[Dict[str, str]]:
    """Scrape PM jobs from a FacetWP-powered WordPress careers site."""
    jobs = []
    seen_ids = set()
    last_page = 1

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=60000, wait_until='networkidle')
            page.wait_for_timeout(3000)

            # Detect last page number
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            last_page_el = soup.find(class_='facetwp-page last')
            last_page = int(last_page_el.get('data-page', 1)) if last_page_el else 1
            print(f"[DEBUG] {company_name}: {last_page} pages detected")

            # Parse page 1
            for job in _parse_template(html, url, company_name):
                if job['id'] not in seen_ids:
                    seen_ids.add(job['id'])
                    jobs.append(job)

            # Paginate through remaining pages
            for page_num in range(2, last_page + 1):
                try:
                    page.click(f'[data-page="{page_num}"]')
                    page.wait_for_timeout(3000)
                    for job in _parse_template(page.content(), url, company_name):
                        if job['id'] not in seen_ids:
                            seen_ids.add(job['id'])
                            jobs.append(job)
                except Exception as e:
                    print(f"[WARN] {company_name}: page {page_num} failed: {e}")
                    break

            browser.close()

    except Exception as e:
        print(f"Error scraping FacetWP for {company_name}: {e}")

    print(f"[DEBUG] {company_name}: {len(jobs)} PM jobs found across {last_page} pages")
    return jobs
