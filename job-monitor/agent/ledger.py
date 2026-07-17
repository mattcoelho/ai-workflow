"""Persistent job-agent ledger and run audit storage."""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from agent.feedback import DEFAULT_DATA_DIR, feedback_id

DEFAULT_LEDGER_FILE = os.getenv(
    "JOB_LEDGER_FILE",
    os.path.join(DEFAULT_DATA_DIR, "job_ledger.jsonl"),
)
DEFAULT_RUN_AUDIT_FILE = os.getenv(
    "JOB_RUN_AUDIT_FILE",
    os.path.join(DEFAULT_DATA_DIR, "run_audits.jsonl"),
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return str(uuid.uuid4())


def description_hash(job: Dict[str, Any]) -> str:
    description = str(job.get("description", "") or "")
    if not description:
        return ""
    return hashlib.sha256(description.encode("utf-8")).hexdigest()[:16]


def ledger_entry(job: Dict[str, Any], run_id: str, sent_in_email: bool) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "evaluated_at": now_iso(),
        "feedback_id": job.get("feedback_id") or feedback_id(job),
        "job_id": job.get("id", ""),
        "company": job.get("company", ""),
        "title": job.get("title", ""),
        "location": job.get("location", ""),
        "url": job.get("url", ""),
        "description_hash": description_hash(job),
        "description_source": job.get("description_source", ""),
        "score": job.get("score"),
        "fit_tier": job.get("fit_tier", ""),
        "reason": job.get("reason", ""),
        "summary": job.get("summary", ""),
        "competitive_angle": job.get("competitive_angle", ""),
        "evidence": job.get("evidence", []),
        "concerns": job.get("concerns", []),
        "extraction": job.get("extraction", {}),
        "verification": job.get("verification", {}),
        "url_repair": job.get("url_repair", {}),
        "calibration": job.get("calibration", {}),
        "sent_in_email": bool(sent_in_email),
    }


def append_jsonl(record: Dict[str, Any], path: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def append_ledger_entry(
    job: Dict[str, Any],
    run_id: str,
    sent_in_email: bool,
    path: str = DEFAULT_LEDGER_FILE,
) -> None:
    append_jsonl(ledger_entry(job, run_id, sent_in_email), path)


def append_run_audit(audit: Dict[str, Any], path: str = DEFAULT_RUN_AUDIT_FILE) -> None:
    append_jsonl(audit, path)


def _score_as_int(job: Dict[str, Any]) -> int:
    try:
        return int(job.get("score", 0) or 0)
    except (TypeError, ValueError):
        return 0


def email_feedback_ids(
    competitive_jobs_by_company: Dict[str, List[Dict[str, Any]]],
    low_jobs_by_company: Dict[str, List[Dict[str, Any]]],
    errors: List[str] = None,
) -> set:
    """Mirror email selection so ledger sent_in_email stays accurate."""
    selected = set()
    total_competitive = sum(len(jobs) for jobs in competitive_jobs_by_company.values())

    for jobs in competitive_jobs_by_company.values():
        for job in jobs:
            selected.add(job.get("feedback_id") or feedback_id(job))

    if total_competitive == 0 and not errors:
        all_low_jobs = [job for jobs in (low_jobs_by_company or {}).values() for job in jobs]
        watchlist_jobs = [
            job for job in all_low_jobs
            if 5 <= _score_as_int(job) <= 6
        ]
        for job in sorted(watchlist_jobs, key=_score_as_int, reverse=True)[:3]:
            selected.add(job.get("feedback_id") or feedback_id(job))

    return selected
