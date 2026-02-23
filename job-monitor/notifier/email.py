"""Email notification module using Gmail SMTP."""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def _format_job_url(url: str, company_name: str) -> str:
    """
    Format job URL for display in email.
    
    Args:
        url: The job URL to format
        company_name: The company name
        
    Returns:
        Formatted URL string
    """
    # For Twilio, format URLs to show clean format
    if "Twilio" in company_name or "twilio.com" in url.lower():
        parsed = urlparse(url)
        # If URL already matches the desired format, return as-is
        if parsed.netloc == "jobs.twilio.com" and parsed.path == "/careers":
            return url
        # Otherwise, try to extract and format to the standard pattern
        # Extract pid from query params if present
        query_params = parse_qs(parsed.query)
        pid = query_params.get('pid', ['1099549995199'])[0] if query_params.get('pid') else '1099549995199'
        return f"https://jobs.twilio.com/careers?pid={pid}"
    
    # For other companies, return URL as-is
    return url


def send_email(new_jobs_by_company: Dict[str, List[Dict[str, str]]], errors: List[str] = None) -> bool:
    """
    Send email notification with new PM jobs.
    
    Args:
        new_jobs_by_company: Dict mapping company names to lists of new job dicts
        errors: Optional list of error messages to include
        
    Returns:
        True if email sent successfully, False otherwise
    """
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    
    if not gmail_user or not gmail_password:
        print("Error: GMAIL_USER and GMAIL_APP_PASSWORD environment variables must be set")
        return False
    
    # Build email body
    body_lines = []
    
    # Count total new jobs
    total_new_jobs = sum(len(jobs) for jobs in new_jobs_by_company.values())
    
    if total_new_jobs == 0 and not errors:
        body_lines.append("No new PM listings scored 6+ today.")
    else:
        # Header
        body_lines.append(f"📋 {total_new_jobs} new PM job(s) matched your profile today\n")
        
        # Group by company
        for company_name in sorted(new_jobs_by_company.keys()):
            jobs = new_jobs_by_company[company_name]
            if jobs:
                for job in jobs:
                    formatted_url = _format_job_url(job.get('url', ''), company_name)
                    score = job.get('score', 'N/A')
                    title = job.get('title', '')
                    location = job.get('location', '') or "Location not specified"
                    summary = job.get('summary', '')
                    reason = job.get('reason', '')
                    
                    body_lines.append(f"[{score}/10] {title} — {company_name}")
                    body_lines.append(f"📍 {location}")
                    body_lines.append(summary)
                    body_lines.append(f"💡 {reason}")
                    body_lines.append(f"🔗 {formatted_url}")
                    body_lines.append("─────────────────────")
        
        # Add errors if any
        if errors:
            body_lines.append("\n\nErrors encountered:")
            for error in errors:
                body_lines.append(f"  • {error}")
    
    body = "\n".join(body_lines)
    
    # Create email
    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = gmail_user
    date_str = datetime.now().strftime("%Y-%m-%d")
    msg["Subject"] = f"🧑‍💼 New PM Jobs – {date_str}"
    
    msg.attach(MIMEText(body, "plain"))
    
    # Send email
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.send_message(msg)
        server.quit()
        print(f"Email sent successfully to {gmail_user}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
