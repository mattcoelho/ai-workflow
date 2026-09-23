"""Build and score a human-labeled benchmark from job feedback."""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from agent.feedback import DEFAULT_FEEDBACK_FILE, load_feedback
from agent.ledger import DEFAULT_LEDGER_FILE
from ai.analyzer import ANALYZER_VERSION, GEMINI_MODEL, analyze_job, fit_tier_for_score

DEFAULT_REPORT_FILE = os.getenv(
    "JOB_EVALUATION_REPORT_FILE",
    os.path.join(os.path.dirname(DEFAULT_FEEDBACK_FILE), "evaluation_report.json"),
)

FIT_LABEL_RANGES = {
    "bullseye": (9, 10),
    "strong_match": (8, 8),
    "competitive_match": (7, 7),
    "applied": (8, 10),
    "interviewed": (9, 10),
    "maybe": (5, 6),
    "ignored": (1, 6),
    "bad_match": (1, 4),
    "wrong_role": (1, 4),
    "wrong_location": (1, 5),
}
BULLSEYE_LABELS = {"bullseye", "strong_match", "applied", "interviewed"}
COMPETITIVE_LABELS = BULLSEYE_LABELS | {"competitive_match"}


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def latest_ledger_entries(path: str = DEFAULT_LEDGER_FILE) -> Dict[str, Dict[str, Any]]:
    latest = {}
    for entry in load_jsonl(path):
        feedback_key = str(entry.get("feedback_id", "") or "")
        if feedback_key:
            latest[feedback_key] = entry
    return latest


def snapshot_from_ledger(entry: Dict[str, Any]) -> Dict[str, Any]:
    calibration = entry.get("calibration") or {}
    raw_score = calibration.get("original_score", entry.get("score"))
    return {
        "feedback_id": entry.get("feedback_id", ""),
        "job_id": entry.get("job_id", ""),
        "company": entry.get("company", ""),
        "title": entry.get("title", ""),
        "location": entry.get("location", ""),
        "url": entry.get("url", ""),
        "description": entry.get("description", ""),
        "description_hash": entry.get("description_hash", ""),
        "description_source": entry.get("description_source", ""),
        "score": raw_score,
        "fit_tier": fit_tier_for_score(int(raw_score or 0)),
        "reason": entry.get("reason", ""),
        "summary": entry.get("summary", ""),
        "competitive_angle": entry.get("competitive_angle", ""),
        "evidence": entry.get("evidence", []),
        "concerns": entry.get("concerns", []),
        "extraction": entry.get("extraction", {}),
        "analyzer_version": entry.get("analyzer_version", "legacy"),
        "model": entry.get("model", "unknown"),
        "evaluated_at": entry.get("evaluated_at", ""),
    }


def benchmark_examples(
    feedback: Optional[Dict[str, Any]] = None,
    ledger_entries: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    feedback = feedback or load_feedback(create=False)
    ledger_entries = ledger_entries if ledger_entries is not None else latest_ledger_entries()
    examples = []
    for feedback_key, value in (feedback.get("jobs") or {}).items():
        item = {"label": value} if isinstance(value, str) else dict(value or {})
        label = str(item.get("label", "") or "").strip().lower()
        if label not in FIT_LABEL_RANGES:
            continue
        snapshot = item.get("snapshot")
        if not isinstance(snapshot, dict):
            ledger_entry = ledger_entries.get(feedback_key)
            snapshot = snapshot_from_ledger(ledger_entry) if ledger_entry else {}
        if not snapshot:
            continue
        examples.append(
            {
                "feedback_id": feedback_key,
                "label": label,
                "notes": str(item.get("notes", "") or ""),
                "snapshot": snapshot,
            }
        )
    return examples


def _prediction_score(example: Dict[str, Any], prediction_key: str) -> Optional[int]:
    prediction = example.get(prediction_key) if prediction_key != "snapshot" else example.get("snapshot")
    if not isinstance(prediction, dict):
        return None
    try:
        return int(prediction.get("score"))
    except (TypeError, ValueError):
        return None


def evaluate_examples(
    examples: Iterable[Dict[str, Any]],
    prediction_key: str = "snapshot",
) -> Dict[str, Any]:
    rows = []
    for example in examples:
        score = _prediction_score(example, prediction_key)
        if score is None:
            continue
        prediction = example.get(prediction_key) if prediction_key != "snapshot" else example.get("snapshot")
        prediction = prediction if isinstance(prediction, dict) else {}
        label = example["label"]
        minimum, maximum = FIT_LABEL_RANGES[label]
        rows.append(
            {
                "feedback_id": example["feedback_id"],
                "label": label,
                "score": score,
                "fit_tier": fit_tier_for_score(score),
                "within_expected_range": minimum <= score <= maximum,
                "reason": prediction.get("reason", ""),
                "concerns": prediction.get("concerns", []),
                "extraction": prediction.get("extraction", {}),
            }
        )

    def precision_at(threshold: int, relevant_labels: set) -> Optional[float]:
        predicted = [row for row in rows if row["score"] >= threshold]
        if not predicted:
            return None
        relevant = sum(row["label"] in relevant_labels for row in predicted)
        return round(relevant / len(predicted), 3)

    positives = [row for row in rows if row["label"] in COMPETITIVE_LABELS]
    competitive_recall = None
    if positives:
        competitive_recall = round(sum(row["score"] >= 7 for row in positives) / len(positives), 3)

    return {
        "examples": len(rows),
        "range_accuracy": round(sum(row["within_expected_range"] for row in rows) / len(rows), 3) if rows else None,
        "bullseye_precision": precision_at(9, BULLSEYE_LABELS),
        "competitive_precision": precision_at(7, COMPETITIVE_LABELS),
        "competitive_recall": competitive_recall,
        "rows": rows,
    }


def rescore_examples(examples: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is required for --rescore")
    errors = []
    for example in examples:
        snapshot = example["snapshot"]
        if not str(snapshot.get("description", "") or "").strip():
            errors.append(f"{example['feedback_id']}: no saved description; cannot replay")
            continue
        job = {
            "id": snapshot.get("job_id", ""),
            "company": snapshot.get("company", ""),
            "title": snapshot.get("title", ""),
            "location": snapshot.get("location", ""),
            "url": snapshot.get("url", ""),
            "description": snapshot.get("description", ""),
        }
        candidate = analyze_job(job)
        if candidate.get("reason") in {"Analysis unavailable", "No API key"}:
            errors.append(f"{example['feedback_id']}: {candidate.get('reason')}")
            example["candidate_error"] = candidate
            continue
        example["candidate"] = candidate
    return examples, errors


def build_report(examples: List[Dict[str, Any]], include_candidate: bool = False) -> Dict[str, Any]:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analyzer_version": ANALYZER_VERSION,
        "model": GEMINI_MODEL,
        "baseline": evaluate_examples(examples),
    }
    if include_candidate:
        report["candidate"] = evaluate_examples(examples, prediction_key="candidate")
    return report


def save_report(report: Dict[str, Any], path: str = DEFAULT_REPORT_FILE) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
