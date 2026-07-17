"""Email notification module using Gmail SMTP."""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Any, List, Dict

from agent.feedback import DEFAULT_FEEDBACK_FILE, feedback_id


def _score_as_int(job: Dict[str, str]) -> int:
    try:
        return int(job.get("score", 0))
    except (TypeError, ValueError):
        return 0


def _tier_for_job(job: Dict[str, str]) -> str:
    tier = str(job.get("fit_tier", "") or "").strip()
    if tier:
        return tier
    score = _score_as_int(job)
    if score >= 9:
        return "Bullseye"
    if score >= 7:
        return "Competitive"
    if score >= 5:
        return "Watchlist"
    return "Low Fit"


def _format_job_url(url: str, company_name: str) -> str:
    """
    Format job URL for display in email.
    
    Args:
        url: The job URL to format
        company_name: The company name
        
    Returns:
        Formatted URL string
    """
    return url


def _format_list(value) -> str:
    if isinstance(value, list):
        return "; ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _append_agent_audit(body_lines: List[str], run_audit: Dict[str, Any]) -> None:
    if not run_audit:
        return

    stats = run_audit.get("stats", {}) or {}
    body_lines.append("\nAgent self-check")
    body_lines.append(
        "Scraped {scraped} job(s), evaluated {evaluated} candidate(s), sent {sent}, held {held}.".format(
            scraped=stats.get("scraped_jobs", 0),
            evaluated=stats.get("evaluated_jobs", 0),
            sent=stats.get("sent_in_email", 0),
            held=stats.get("held_jobs", 0),
        )
    )
    body_lines.append(
        "Dedupe: {dupes} removed. Verification issues: {issues}. Calibration applied: {calibrated}.".format(
            dupes=stats.get("duplicate_jobs", 0),
            issues=stats.get("verification_issues", 0),
            calibrated=stats.get("calibrated_jobs", 0),
        )
    )
    body_lines.append(
        "URL repair: {attempts} attempt(s), {fixed} fixed, {failed} unresolved.".format(
            attempts=stats.get("url_repair_attempts", 0),
            fixed=stats.get("url_repairs", 0),
            failed=stats.get("url_repair_failures", 0),
        )
    )

    issues = run_audit.get("issues", []) or []
    if issues:
        body_lines.append("Top self-check notes:")
        for issue in issues[:4]:
            body_lines.append(f"  - {issue}")

    calibrations = run_audit.get("calibrations", []) or []
    if calibrations:
        body_lines.append("Calibration notes:")
        for calibration in calibrations[:4]:
            body_lines.append(f"  - {calibration}")

    feedback_file = run_audit.get("feedback_file") or DEFAULT_FEEDBACK_FILE
    body_lines.append(
        f"Feedback loop: edit {feedback_file} using a job's Feedback ID "
        "with label strong_match, maybe, bad_match, bad_url, wrong_role, applied, or interviewed."
    )


def _append_job(body_lines: List[str], job: Dict[str, str], company_name: str) -> None:
    formatted_url = _format_job_url(job.get('url', ''), company_name)
    score = job.get('score', 'N/A')
    title = job.get('title', '')
    location = job.get('location', '') or "Location not specified"
    summary = job.get('summary', '')
    reason = job.get('reason', '')
    angle = job.get('competitive_angle', '')
    evidence = _format_list(job.get('evidence'))
    concerns = _format_list(job.get('concerns'))
    job_feedback_id = job.get("feedback_id") or feedback_id(job)

    body_lines.append(f"[{score}/10] {title} — {company_name}")
    body_lines.append(f"📍 {location}")
    if summary:
        body_lines.append(summary)
    if angle:
        body_lines.append(f"🎯 {angle}")
    if evidence:
        body_lines.append(f"✅ {evidence}")
    if concerns:
        body_lines.append(f"⚠️ {concerns}")
    if reason:
        body_lines.append(f"💡 {reason}")
    body_lines.append(f"🔗 {formatted_url}")
    body_lines.append(f"🧠 Feedback ID: {job_feedback_id}")
    body_lines.append("─────────────────────")


def send_email(
    new_jobs_by_company: Dict[str, List[Dict[str, str]]],
    low_jobs_by_company: Dict[str, List[Dict[str, str]]] = None,
    errors: List[str] = None,
    run_audit: Dict[str, Any] = None,
) -> bool:
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
    
    total_new_jobs = sum(len(jobs) for jobs in new_jobs_by_company.values())
    all_low_jobs = [job for jobs in (low_jobs_by_company or {}).values() for job in jobs]

    if total_new_jobs == 0 and not errors:
        watchlist_jobs = [job for job in all_low_jobs if 5 <= _score_as_int(job) <= 6]
        if watchlist_jobs:
            top_low = sorted(watchlist_jobs, key=_score_as_int, reverse=True)[:3]
            body_lines.append(f"No Bullseye or Competitive roles today. Watchlist role(s) found — top {len(top_low)}:\n")
            body_lines.append("Watchlist (5-6)")
            for job in top_low:
                _append_job(body_lines, job, job.get('company', ''))
        else:
            body_lines.append("No interview-ready or watchlist product roles found today")
    else:
        # Header
        body_lines.append(f"📋 {total_new_jobs} competitive PM job(s) matched your profile today\n")

        for section_title, tiers in (
            ("Bullseye (9-10)", {"Bullseye"}),
            ("Competitive (7-8)", {"Competitive"}),
        ):
            section_jobs = []
            for company_name, jobs in new_jobs_by_company.items():
                for job in jobs:
                    if _tier_for_job(job) in tiers:
                        section_jobs.append((company_name, job))

            if section_jobs:
                body_lines.append(section_title)
                for company_name, job in sorted(section_jobs, key=lambda item: (-_score_as_int(item[1]), item[0])):
                    _append_job(body_lines, job, company_name)
        
        # Add errors if any
        if errors:
            body_lines.append("\n\nErrors encountered:")
            for error in errors:
                body_lines.append(f"  • {error}")

    _append_agent_audit(body_lines, run_audit)
    
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
