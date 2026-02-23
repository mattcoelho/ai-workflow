"""Email notification module using Gmail SMTP."""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict


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
        body_lines.append("No new PM listings today.")
    else:
        # Group by company
        for company_name in sorted(new_jobs_by_company.keys()):
            jobs = new_jobs_by_company[company_name]
            if jobs:
                body_lines.append(f"\n{company_name}:")
                for job in jobs:
                    body_lines.append(f"  • {job['title']} - {job['url']}")
        
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
