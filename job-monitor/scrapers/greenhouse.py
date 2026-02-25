"""Greenhouse job board scraper."""

import re
import requests
from typing import List, Dict


def scrape_greenhouse(board_token: str, company_name: str) -> List[Dict[str, str]]:
    """
    Scrape Product Manager jobs from Greenhouse job board.
    
    Args:
        board_token: Greenhouse board token
        company_name: Company name for the returned job dicts
        
    Returns:
        List of job dicts with keys: id, title, location, url, company
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        jobs = []
        for job in data.get("jobs", []):
            title = job.get("title", "")
            # Filter for Product Manager positions (case-insensitive)
            if re.search(r'product manager|platform manager|product lead|group product|staff product|head of product|director of product', title.lower()):
                jobs.append({
                    "id": str(job.get("id", "")),
                    "title": title,
                    "location": job.get("location", {}).get("name", ""),
                    "url": job.get("absolute_url", ""),
                    "company": company_name
                })
        
        return jobs
    except Exception as e:
        # Return empty list on error, caller will handle error reporting
        print(f"Error scraping Greenhouse for {company_name}: {e}")
        return []
