# Export every feedback report to a CSV file (newest first)

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from db.DataBase import db
from db.feedback import CATEGORIES, STATUSES

COLUMNS = [
    "id", "created_at_utc", "status", "category", "role", "name", "email", "classes",
    "page", "message", "note", "updated_at_utc", "resolved_at_utc",
]
IDENTITY_COLUMNS = {"name", "email"}


def fetch_reports(status=None, category=None):
    # All reports with the reporter's name and email and their class names, newest first.
    match = {}
    if status:
        match["status"] = status
    if category:
        match["category"] = category
    pipeline = ([{"$match": match}] if match else []) + [
        {"$sort": {"created_at": -1, "_id": -1}},
        {"$lookup": {
            "from": "users", "localField": "user_id", "foreignField": "_id", "as": "user",
            "pipeline": [{"$project": {"first_name": 1, "last_name": 1, "email": 1}}],
        }},
        {"$set": {"user": {"$arrayElemAt": ["$user", 0]}}},
        {"$lookup": {
            "from": "classes", "localField": "class_ids", "foreignField": "_id", "as": "classes",
            "pipeline": [{"$project": {"name": 1}}],
        }},
    ]
    return db.aggregate("feedback", pipeline)


def _safe(value):
    # Plain text for a cell. A leading = + - @ would run as a formula in Excel or Sheets.
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _when(value):
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)  # Mongo returns naive UTC datetimes
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def report_row(report):
    user = report.get("user") or {}
    name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
    return {
        "id": str(report["_id"]),
        "created_at_utc": _when(report.get("created_at")),
        "status": STATUSES.get(report.get("status"), report.get("status")),
        "category": CATEGORIES.get(report.get("category"), report.get("category")),
        "role": _safe(report.get("role")),
        "name": _safe(name),
        "email": _safe(user.get("email")),
        "classes": _safe("; ".join(row.get("name", "") for row in report.get("classes", []))),
        "page": _safe(report.get("page")),
        "message": _safe(report.get("message")),
        "note": _safe(report.get("note")),
        "updated_at_utc": _when(report.get("updated_at")),
        "resolved_at_utc": _when(report.get("resolved_at")),
    }


def write_csv(reports, path, anonymize=False):
    """Write the reports to ``path`` and return how many rows were written."""
    columns = [column for column in COLUMNS if not (anonymize and column in IDENTITY_COLUMNS)]
    count = 0
    # utf-8-sig so Excel opens accented characters correctly; newline="" so the csv module
    # controls line endings (messages can contain line breaks).
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for report in reports:
            writer.writerow(report_row(report))
            count += 1
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export all feedback reports to a CSV file.")
    parser.add_argument("--out", help="Output file (default: feedback_export_<date>.csv)")
    parser.add_argument("--status", choices=list(STATUSES), help="Only reports with this status")
    parser.add_argument("--category", choices=list(CATEGORIES), help="Only reports of this type")
    parser.add_argument("--anonymize", action="store_true", help="Leave out names and emails")
    args = parser.parse_args(argv)
    path = args.out or f"feedback_export_{datetime.now(timezone.utc):%Y%m%d}.csv"
    try:
        count = write_csv(fetch_reports(args.status, args.category), path, args.anonymize)
    except Exception as error:  # database not configured, unreachable, or the query timed out
        print(f"Could not export feedback: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {count} report(s) to {path}")
    if not args.anonymize:
        print("This file contains student names and emails. Do not commit or share it widely.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
