"""Main orchestration script for job monitoring."""

import json
import os
from typing import Dict, List
from companies import COMPANIES
from scrapers.greenhouse import scrape_greenhouse
from scrapers.ashby import scrape_ashby
from scrapers.static import scrape_static
from scrapers.playwright_scraper import scrape_playwright
from ai.analyzer import analyze_job
from notifier.email import send_email

SEEN_JOBS_FILE = "seen_jobs.json"


def load_seen_jobs() -> Dict[str, List[str]]:
    """Load previously seen job IDs from JSON file."""
    if os.path.exists(SEEN_JOBS_FILE):
        try:
            with open(SEEN_JOBS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading seen_jobs.json: {e}")
            return {}
    return {}


def save_seen_jobs(seen_jobs: Dict[str, List[str]]) -> None:
    """Save seen job IDs to JSON file."""
    try:
        with open(SEEN_JOBS_FILE, "w") as f:
            json.dump(seen_jobs, f, indent=2)
    except Exception as e:
        print(f"Error saving seen_jobs.json: {e}")


def get_new_jobs(all_jobs: List[Dict[str, str]], seen_ids: List[str]) -> List[Dict[str, str]]:
    """Filter out jobs that have been seen before."""
    return [job for job in all_jobs if job["id"] not in seen_ids]


def main():
    """Main orchestration function."""
    # Load previously seen jobs
    seen_jobs = load_seen_jobs()
    
    # Scrape all companies
    all_new_jobs_by_company = {}
    errors = []
    
    for company in COMPANIES:
        company_name = company["name"]
        company_type = company["type"]
        board_token = company["board_token"]
        
        try:
            if company_type == "greenhouse":
                jobs = scrape_greenhouse(board_token, company_name)
            elif company_type == "ashby":
                jobs = scrape_ashby(board_token, company_name)
            elif company_type == "static":
                # For static companies, board_token is the URL
                jobs = scrape_static(board_token, company_name)
            elif company_type == "playwright":
                # For playwright companies, board_token is the URL
                jobs = scrape_playwright(board_token, company_name)
            else:
                error_msg = f"Unknown company type '{company_type}' for {company_name}"
                errors.append(error_msg)
                print(f"{company_name}: ERROR - {error_msg}")
                continue
            
            # Get seen IDs for this company (default to empty list)
            seen_ids = seen_jobs.get(company_name, [])
            
            # Filter to only new jobs
            new_jobs = get_new_jobs(jobs, seen_ids)
            
            # Analyze and filter jobs by score
            filtered_jobs = []
            for job in new_jobs:
                analysis = analyze_job(job)
                job["score"] = analysis["score"]
                job["reason"] = analysis["reason"]
                job["summary"] = analysis["summary"]
                
                if job["score"] < 6:
                    print(f"{company_name}: job '{job['title']}' scored {job['score']}/10 - skipped")
                else:
                    filtered_jobs.append(job)
            
            if filtered_jobs:
                all_new_jobs_by_company[company_name] = filtered_jobs
                # Update seen jobs with all jobs (both new and previously seen)
                all_job_ids = [job["id"] for job in jobs]
                seen_jobs[company_name] = all_job_ids
            else:
                # Still update seen jobs with current job IDs (in case jobs were removed)
                all_job_ids = [job["id"] for job in jobs]
                seen_jobs[company_name] = all_job_ids
            
            # Print summary for this company
            print(f"{company_name}: {len(filtered_jobs)} new jobs found")
                
        except Exception as e:
            error_msg = f"Error processing {company_name}: {e}"
            errors.append(error_msg)
            print(f"{company_name}: ERROR - {e}")
            continue
    
    # Send email notification
    send_email(all_new_jobs_by_company, errors if errors else None)
    
    # Save updated seen jobs
    save_seen_jobs(seen_jobs)
    print("Updated seen_jobs.json")


if __name__ == "__main__":
    main()
