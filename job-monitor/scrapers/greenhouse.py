"""Greenhouse job board scraper."""

import re
import requests
from typing import List, Dict
from scrapers.job_details import extract_greenhouse_description


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
            description = extract_greenhouse_description(job.get("content", ""))
            jobs.append({
                "id": str(job.get("id", "")),
                "title": title,
                "location": job.get("location", {}).get("name", ""),
                "url": job.get("absolute_url", ""),
                "company": company_name,
                "description": description,
                "description_source": "greenhouse_api" if description else "unavailable"
            })
        
        return jobs
    except Exception as e:
        # Return empty list on error, caller will handle error reporting
        print(f"Error scraping Greenhouse for {company_name}: {e}")
        return []
