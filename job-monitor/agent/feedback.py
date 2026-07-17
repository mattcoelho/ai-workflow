"""Feedback-driven calibration for job scoring."""

import json
import os
from typing import Any, Dict, List

from ai.analyzer import fit_tier_for_score

DEFAULT_DATA_DIR = os.getenv("JOB_AGENT_DATA_DIR", "data")
DEFAULT_FEEDBACK_FILE = os.getenv(
    "JOB_FEEDBACK_FILE",
    os.path.join(DEFAULT_DATA_DIR, "feedback.json"),
)

VALID_LABELS = {
    "strong_match",
    "maybe",
    "bad_match",
    "bad_url",
    "wrong_role",
    "ignored",
    "applied",
    "interviewed",
}

DEFAULT_FEEDBACK = {
    "labels": sorted(VALID_LABELS),
    "jobs": {},
    "rules": [],
    "company_adjustments": {},
}


def feedback_id(job: Dict[str, Any]) -> str:
    """Stable user-facing key for feedback.json."""
    company = str(job.get("company", "") or "Unknown").strip()
    job_id = str(job.get("id", "") or "").strip()
    if not job_id:
        job_id = str(job.get("url", "") or job.get("title", "") or "unknown").strip()
    return f"{company}::{job_id}"


def load_feedback(path: str = DEFAULT_FEEDBACK_FILE, create: bool = True) -> Dict[str, Any]:
    """Load feedback rules and direct job labels."""
    if not os.path.exists(path):
        feedback = dict(DEFAULT_FEEDBACK)
        if create:
            try:
                save_feedback(feedback, path)
            except Exception as exc:
                print(f"[WARN] Could not create feedback file {path}: {exc}")
        return feedback

    try:
        with open(path, "r") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"[WARN] Could not load feedback file {path}: {exc}")
        return dict(DEFAULT_FEEDBACK)

    if not isinstance(data, dict):
        return dict(DEFAULT_FEEDBACK)

    feedback = dict(DEFAULT_FEEDBACK)
    feedback.update(data)
    feedback.setdefault("jobs", {})
    feedback.setdefault("rules", [])
    feedback.setdefault("company_adjustments", {})
    feedback.setdefault("labels", sorted(VALID_LABELS))
    return feedback


def save_feedback(feedback: Dict[str, Any], path: str = DEFAULT_FEEDBACK_FILE) -> None:
    """Persist feedback, creating the data directory as needed."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w") as f:
        json.dump(feedback, f, indent=2, sort_keys=True)


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _contains_all(haystack: str, needles: Any) -> bool:
    values = _as_list(needles)
    if not values:
        return True
    lower = haystack.lower()
    return all(value.lower() in lower for value in values)


def _matches_rule(job: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    if not isinstance(rule, dict):
        return False

    company = str(job.get("company", "") or "")
    title = str(job.get("title", "") or "")
    location = str(job.get("location", "") or "")
    url = str(job.get("url", "") or "")
    description = str(job.get("description", "") or "")

    if rule.get("company") and str(rule["company"]).lower() != company.lower():
        return False
    if not _contains_all(title, rule.get("title_contains")):
        return False
    if not _contains_all(location, rule.get("location_contains")):
        return False
    if not _contains_all(url, rule.get("url_contains")):
        return False
    if not _contains_all(description, rule.get("description_contains")):
        return False
    return True


def _set_score(job: Dict[str, Any], score: int) -> None:
    score = max(1, min(10, int(score)))
    job["score"] = score
    job["fit_tier"] = fit_tier_for_score(score)


def _append_field(job: Dict[str, Any], key: str, value: str, max_items: int = 6) -> None:
    if not value:
        return
    existing = job.get(key)
    if not isinstance(existing, list):
        existing = [existing] if existing else []
    if value not in existing:
        existing.append(value)
    job[key] = existing[:max_items]


def _apply_label(job: Dict[str, Any], label: str, source: str, notes: str = "") -> List[str]:
    label = str(label or "").strip().lower()
    if label not in VALID_LABELS:
        return []

    changes = []
    score = int(job.get("score", 0) or 0)
    label_note = notes or source

    if label in {"bad_match", "wrong_role"}:
        new_score = min(score, 4)
        _set_score(job, new_score)
        _append_field(job, "concerns", f"Feedback marked this pattern as {label.replace('_', ' ')}.")
        changes.append(f"{source}: capped at {new_score} from {score} ({label})")
    elif label == "bad_url":
        new_score = min(score, 3)
        _set_score(job, new_score)
        _append_field(job, "concerns", "Feedback marked this job URL as inaccurate.")
        changes.append(f"{source}: capped at {new_score} from {score} (bad URL)")
    elif label in {"maybe", "ignored"}:
        new_score = min(score, 6)
        _set_score(job, new_score)
        _append_field(job, "concerns", f"Feedback marked this as {label}; keep as watchlist.")
        changes.append(f"{source}: capped at {new_score} from {score} ({label})")
    elif label == "strong_match":
        new_score = max(score, 8)
        _set_score(job, new_score)
        _append_field(job, "evidence", f"Feedback marked similar role as strong match: {label_note}")
        changes.append(f"{source}: raised floor to {new_score} ({label})")
    elif label == "applied":
        new_score = max(score, 8)
        _set_score(job, new_score)
        _append_field(job, "evidence", f"Applied signal from feedback: {label_note}")
        changes.append(f"{source}: raised floor to {new_score} ({label})")
    elif label == "interviewed":
        new_score = max(score, 9)
        _set_score(job, new_score)
        _append_field(job, "evidence", f"Interview signal from feedback: {label_note}")
        changes.append(f"{source}: raised floor to {new_score} ({label})")

    return changes


def _apply_rule_action(job: Dict[str, Any], rule: Dict[str, Any]) -> List[str]:
    changes = []
    source = str(rule.get("name") or "feedback rule")
    original_score = int(job.get("score", 0) or 0)

    if "score_delta" in rule:
        try:
            _set_score(job, original_score + int(rule["score_delta"]))
            changes.append(f"{source}: score delta {rule['score_delta']}")
        except (TypeError, ValueError):
            pass

    if "cap" in rule:
        try:
            cap = int(rule["cap"])
            if int(job.get("score", 0) or 0) > cap:
                _set_score(job, cap)
                changes.append(f"{source}: capped at {cap}")
        except (TypeError, ValueError):
            pass

    if "floor" in rule:
        try:
            floor = int(rule["floor"])
            if int(job.get("score", 0) or 0) < floor:
                _set_score(job, floor)
                changes.append(f"{source}: raised floor to {floor}")
        except (TypeError, ValueError):
            pass

    if rule.get("label"):
        changes.extend(_apply_label(job, str(rule["label"]), source, str(rule.get("notes", ""))))

    if rule.get("concern"):
        _append_field(job, "concerns", str(rule["concern"]))
    if rule.get("evidence"):
        _append_field(job, "evidence", str(rule["evidence"]))

    return changes


def apply_feedback_calibration(job: Dict[str, Any], feedback: Dict[str, Any]) -> Dict[str, Any]:
    """Apply direct user feedback and reusable rules to a scored job."""
    job.setdefault("feedback_id", feedback_id(job))
    original_score = int(job.get("score", 0) or 0)
    changes: List[str] = []

    company_adjustments = feedback.get("company_adjustments", {})
    company = str(job.get("company", "") or "")
    if isinstance(company_adjustments, dict) and company in company_adjustments:
        try:
            delta = int(company_adjustments[company])
            _set_score(job, original_score + delta)
            changes.append(f"company adjustment {company}: {delta:+d}")
        except (TypeError, ValueError):
            pass

    for rule in feedback.get("rules", []) or []:
        if _matches_rule(job, rule):
            changes.extend(_apply_rule_action(job, rule))

    direct_feedback = (feedback.get("jobs") or {}).get(job["feedback_id"])
    if isinstance(direct_feedback, str):
        changes.extend(_apply_label(job, direct_feedback, "direct feedback"))
    elif isinstance(direct_feedback, dict):
        changes.extend(
            _apply_label(
                job,
                str(direct_feedback.get("label", "")),
                "direct feedback",
                str(direct_feedback.get("notes", "")),
            )
        )
        if direct_feedback.get("notes"):
            _append_field(job, "concerns", f"Feedback note: {direct_feedback['notes']}")

    adjusted_score = int(job.get("score", 0) or 0)
    job["calibration"] = {
        "original_score": original_score,
        "adjusted_score": adjusted_score,
        "applied": changes,
    }
    return job
