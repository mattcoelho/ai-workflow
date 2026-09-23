"""Label job-monitor results and evaluate scoring against human feedback."""

import argparse
import json
from datetime import datetime, timezone

from agent.evaluation import (
    DEFAULT_REPORT_FILE,
    benchmark_examples,
    build_report,
    latest_ledger_entries,
    rescore_examples,
    save_report,
    snapshot_from_ledger,
)
from agent.feedback import DEFAULT_FEEDBACK_FILE, VALID_LABELS, load_feedback, save_feedback


def label_job(args: argparse.Namespace) -> int:
    feedback = load_feedback(args.feedback_file)
    ledger = latest_ledger_entries(args.ledger_file)
    entry = ledger.get(args.feedback_id)
    if not entry:
        print(f"Feedback ID not found in ledger: {args.feedback_id}")
        return 1

    existing = (feedback.get("jobs") or {}).get(args.feedback_id)
    existing = dict(existing) if isinstance(existing, dict) else {}
    existing.update(
        {
            "label": args.label,
            "notes": args.notes or existing.get("notes", ""),
            "labeled_at": datetime.now(timezone.utc).isoformat(),
            "snapshot": snapshot_from_ledger(entry),
        }
    )
    feedback.setdefault("jobs", {})[args.feedback_id] = existing
    save_feedback(feedback, args.feedback_file)
    print(f"Labeled {args.feedback_id} as {args.label}")
    return 0


def list_jobs(args: argparse.Namespace) -> int:
    entries = list(latest_ledger_entries(args.ledger_file).values())
    if args.sent_only:
        entries = [entry for entry in entries if entry.get("sent_in_email")]
    entries.sort(key=lambda entry: str(entry.get("evaluated_at", "")), reverse=True)
    for entry in entries[: args.limit]:
        print(
            f"{entry.get('feedback_id')} | {entry.get('score')}/10 | "
            f"{entry.get('title')} | {entry.get('location', '')}"
        )
    return 0


def evaluate(args: argparse.Namespace) -> int:
    feedback = load_feedback(args.feedback_file, create=False)
    examples = benchmark_examples(feedback, latest_ledger_entries(args.ledger_file))
    errors = []
    if args.rescore:
        examples, errors = rescore_examples(examples)
    report = build_report(examples, include_candidate=args.rescore)
    if errors:
        report["replay_errors"] = errors
    save_report(report, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"Saved evaluation report to {args.output}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.set_defaults(feedback_file=DEFAULT_FEEDBACK_FILE, ledger_file="data/job_ledger.jsonl")
    subcommands = root.add_subparsers(dest="command", required=True)

    label = subcommands.add_parser("label", help="Attach a human label and preserve a benchmark snapshot.")
    label.add_argument("feedback_id")
    label.add_argument("label", choices=sorted(VALID_LABELS))
    label.add_argument("--notes", default="")
    label.add_argument("--feedback-file", default=DEFAULT_FEEDBACK_FILE)
    label.add_argument("--ledger-file", default="data/job_ledger.jsonl")
    label.set_defaults(func=label_job)

    listing = subcommands.add_parser("list", help="List recent jobs and their Feedback IDs.")
    listing.add_argument("--limit", type=int, default=20)
    listing.add_argument("--sent-only", action="store_true")
    listing.add_argument("--ledger-file", default="data/job_ledger.jsonl")
    listing.set_defaults(func=list_jobs)

    evaluation = subcommands.add_parser("evaluate", help="Measure scoring quality against labeled jobs.")
    evaluation.add_argument("--rescore", action="store_true", help="Call Gemini once per replayable labeled job.")
    evaluation.add_argument("--output", default=DEFAULT_REPORT_FILE)
    evaluation.add_argument("--feedback-file", default=DEFAULT_FEEDBACK_FILE)
    evaluation.add_argument("--ledger-file", default="data/job_ledger.jsonl")
    evaluation.set_defaults(func=evaluate)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
