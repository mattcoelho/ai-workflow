"""Ashby job board scraper."""

import requests
from typing import List, Dict


def scrape_ashby(board_token: str, company_name: str) -> List[Dict[str, str]]:
    """
    Scrape Product Manager jobs from Ashby job board.
    
    Args:
        board_token: Ashby board token
        company_name: Company name for the returned job dicts
        
    Returns:
        List of job dicts with keys: id, title, location, url, company
    """
    url = f"https://api.ashbyhq.com/posting-public/job/list?organizationHostedJobsPageName={board_token}"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        jobs = []
        for job in data.get("jobs", []):
            title = job.get("title", "")
            # Filter for Product Manager positions (case-insensitive)
            if "product manager" in title.lower():
                jobs.append({
                    "id": str(job.get("id", "")),
                    "title": title,
                    "location": job.get("locationName", ""),
                    "url": job.get("jobUrl", ""),
                    "company": company_name
                })
        
        return jobs
    except Exception as e:
        # Return empty list on error, caller will handle error reporting
        print(f"Error scraping Ashby for {company_name}: {e}")
        return []
