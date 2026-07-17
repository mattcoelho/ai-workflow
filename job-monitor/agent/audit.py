"""Run-level audit summary for the job agent."""

from typing import Any, Dict, List

from agent.feedback import DEFAULT_FEEDBACK_FILE
from agent.ledger import new_run_id, now_iso


class RunAudit:
    """Collect lightweight self-observation during a monitor run."""

    def __init__(self, run_id: str = None):
        self.run_id = run_id or new_run_id()
        self.started_at = now_iso()
        self.stats = {
            "companies": 0,
            "scraped_jobs": 0,
            "new_jobs": 0,
            "title_candidates": 0,
            "evaluated_jobs": 0,
            "competitive_jobs": 0,
            "held_jobs": 0,
            "sent_in_email": 0,
            "duplicate_jobs": 0,
            "verification_issues": 0,
            "calibrated_jobs": 0,
        }
        self.company_stats: Dict[str, Dict[str, int]] = {}
        self.issues: List[str] = []
        self.calibrations: List[str] = []
        self.errors: List[str] = []

    def _company(self, company: str) -> Dict[str, int]:
        if company not in self.company_stats:
            self.company_stats[company] = {
                "scraped": 0,
                "new": 0,
                "candidates": 0,
                "evaluated": 0,
                "competitive": 0,
                "held": 0,
            }
        return self.company_stats[company]

    def record_scrape(self, company: str, scraped_count: int) -> None:
        self.stats["companies"] += 1
        self.stats["scraped_jobs"] += scraped_count
        self._company(company)["scraped"] = scraped_count

    def record_duplicates(self, duplicate_notes: List[str]) -> None:
        if not duplicate_notes:
            return
        self.stats["duplicate_jobs"] += len(duplicate_notes)
        self.issues.extend(duplicate_notes[:5])

    def record_candidates(self, company: str, new_count: int, candidate_count: int) -> None:
        self.stats["new_jobs"] += new_count
        self.stats["title_candidates"] += candidate_count
        company_stats = self._company(company)
        company_stats["new"] = new_count
        company_stats["candidates"] = candidate_count

    def record_evaluated(self, job: Dict[str, Any]) -> None:
        company = str(job.get("company", "") or "")
        self.stats["evaluated_jobs"] += 1
        self._company(company)["evaluated"] += 1

        if int(job.get("score", 0) or 0) >= 7:
            self.stats["competitive_jobs"] += 1
            self._company(company)["competitive"] += 1
        else:
            self.stats["held_jobs"] += 1
            self._company(company)["held"] += 1

        verification = job.get("verification") or {}
        issues = verification.get("issues") or []
        if issues:
            self.stats["verification_issues"] += 1
            self.issues.append(f"{company} - {job.get('title', '')}: {'; '.join(issues)}")

        calibration = job.get("calibration") or {}
        applied = calibration.get("applied") or []
        if applied:
            self.stats["calibrated_jobs"] += 1
            self.calibrations.append(f"{company} - {job.get('title', '')}: {'; '.join(applied)}")

    def record_email_selection(self, selected_count: int) -> None:
        self.stats["sent_in_email"] = selected_count

    def record_error(self, error: str) -> None:
        self.errors.append(error)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": now_iso(),
            "stats": self.stats,
            "company_stats": self.company_stats,
            "issues": self.issues[:12],
            "calibrations": self.calibrations[:12],
            "errors": self.errors[:12],
            "feedback_file": DEFAULT_FEEDBACK_FILE,
        }
