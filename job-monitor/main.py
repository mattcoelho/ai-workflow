"""Main orchestration script for job monitoring."""

import json
import os
import re
from typing import Dict, List
from companies import COMPANIES
from scrapers.greenhouse import scrape_greenhouse
from scrapers.ashby import scrape_ashby
from scrapers.static import scrape_static, scrape_parallel
from scrapers.playwright_scraper import scrape_playwright
from scrapers.facetwp_scraper import scrape_facetwp
from scrapers.job_details import enrich_job_details
from ai.analyzer import analyze_job
from ai.title_filter import is_pm_role
from agent.audit import RunAudit
from agent.feedback import apply_feedback_calibration, feedback_id, load_feedback
from agent.ledger import append_ledger_entry, append_run_audit, email_feedback_ids
from agent.url_repair import repair_job_url
from agent.verification import apply_verification_caps, collapse_duplicate_jobs, verify_job
from notifier.email import send_email

TITLE_FILTER = (
    r'product manager|product lead|group product|staff product|head of product|'
    r'director of product|product operations|technical product manager|\btpm\b|'
    r'program manager|forward deployed|fde'
)

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
    feedback = load_feedback()
    audit = RunAudit()
    evaluated_jobs = []
    
    # Scrape all companies
    all_new_jobs_by_company = {}
    all_low_jobs_by_company = {}
    errors = []
    
    for company in COMPANIES:
        company_name = company["name"]
        company_type = company["type"]
        board_token = company.get("board_token")
        
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
            elif company_type == "facetwp":
                jobs = scrape_facetwp(board_token, company_name)
            elif company_type == "parallel":
                jobs = scrape_parallel(company["company_id"], company_name)
            else:
                error_msg = f"Unknown company type '{company_type}' for {company_name}"
                errors.append(error_msg)
                audit.record_error(error_msg)
                print(f"{company_name}: ERROR - {error_msg}")
                continue

            audit.record_scrape(company_name, len(jobs))
            jobs, duplicate_notes = collapse_duplicate_jobs(jobs)
            audit.record_duplicates(duplicate_notes)
            
            # Get seen IDs for this company (default to empty list)
            seen_ids = seen_jobs.get(company_name, [])
            
            # Filter to only new jobs
            new_jobs = get_new_jobs(jobs, seen_ids)
            new_jobs_count = len(new_jobs)
            filtered_jobs = []
            for job in new_jobs:
                title = job.get("title", "")
                if re.search(TITLE_FILTER, title, re.IGNORECASE):
                    filtered_jobs.append(job)  # fast path, no API call
                elif is_pm_role(title):
                    filtered_jobs.append(job)  # AI catches edge cases
            new_jobs = filtered_jobs
            audit.record_candidates(company_name, new_jobs_count, len(new_jobs))

            # Analyze and filter jobs by score
            filtered_jobs = []
            for job in new_jobs:
                enrich_job_details(job)
                job["feedback_id"] = feedback_id(job)
                repair_job_url(job)
                job["verification"] = job.get("verification") or verify_job(job)
                analysis = analyze_job(job)
                job["score"] = analysis["score"]
                job["reason"] = analysis["reason"]
                job["summary"] = analysis["summary"]
                job["fit_tier"] = analysis.get("fit_tier", "")
                job["competitive_angle"] = analysis.get("competitive_angle", "")
                job["evidence"] = analysis.get("evidence", [])
                job["concerns"] = analysis.get("concerns", [])
                apply_feedback_calibration(job, feedback)
                apply_verification_caps(job)
                evaluated_jobs.append(job)
                audit.record_evaluated(job)
                
                if job["score"] < 7:
                    print(f"{company_name}: job '{job['title']}' scored {job['score']}/10 - skipped")
                    if company_name not in all_low_jobs_by_company:
                        all_low_jobs_by_company[company_name] = []
                    all_low_jobs_by_company[company_name].append(job)
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
            audit.record_error(error_msg)
            print(f"{company_name}: ERROR - {e}")
            continue
    
    selected_feedback_ids = email_feedback_ids(
        all_new_jobs_by_company,
        all_low_jobs_by_company,
        errors if errors else None,
    )
    audit.record_email_selection(len(selected_feedback_ids))
    run_audit = audit.to_dict()

    # Send email notification
    email_sent = send_email(
        all_new_jobs_by_company,
        all_low_jobs_by_company,
        errors if errors else None,
        run_audit=run_audit,
    )

    if not email_sent:
        selected_feedback_ids = set()
        audit.record_email_selection(0)
        run_audit = audit.to_dict()

    try:
        for job in evaluated_jobs:
            append_ledger_entry(
                job,
                audit.run_id,
                (job.get("feedback_id") or feedback_id(job)) in selected_feedback_ids,
            )
        append_run_audit(run_audit)
        print(f"Saved agent ledger for run {audit.run_id}")
    except Exception as e:
        print(f"Error saving agent ledger: {e}")
    
    # Save updated seen jobs
    save_seen_jobs(seen_jobs)
    print("Updated seen_jobs.json")


if __name__ == "__main__":
    main()
