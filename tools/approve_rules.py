#!/usr/bin/env python3
"""Explicit human approval workflow for draft rule JSON files."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Approve specifically reviewed draft rules")
    parser.add_argument("--reviewer", required=True, help="Name, credential")
    parser.add_argument("--slugs", required=True, nargs="+", help="Rule slugs, space- or comma-separated")
    parser.add_argument("--confirm-reviewed", action="store_true", help="Confirm that every selected rule was reviewed")
    args = parser.parse_args()
    if not args.confirm_reviewed:
        parser.error("--confirm-reviewed is required")
    slugs = sorted({slug for item in args.slugs for slug in item.split(",") if slug})
    if not slugs:
        parser.error("--slugs must contain at least one slug")
    files = sorted((ROOT / "data/rules/draft").glob("*.json"))
    found: dict[str, tuple[Path, dict]] = {}
    for path in files:
        items = json.loads(path.read_text())
        if isinstance(items, dict): items = [items]
        for item in items:
            if item.get("slug") in slugs:
                found[item["slug"]] = (path, item)
    missing = sorted(set(slugs) - set(found))
    if missing:
        parser.error("unknown rule slug(s): " + ", ".join(missing))
    reviewed_at = datetime.now(timezone.utc).isoformat()
    touched: dict[Path, list[dict]] = {}
    for slug in slugs:
        path, item = found[slug]
        data = touched.setdefault(path, json.loads(path.read_text()))
        if isinstance(data, dict): data = [data]; touched[path] = data
        for row in data:
            if row.get("slug") == slug:
                row["status"] = "APPROVED"
                row["reviewed_by"] = args.reviewer
                row["reviewed_at"] = reviewed_at
    for path, data in touched.items():
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    approvals = ROOT / "docs/approvals.md"
    with approvals.open("a", encoding="utf-8") as handle:
        handle.write(f"- {reviewed_at}: {args.reviewer} approved: {', '.join(slugs)}\n")
    print(f"Approved {len(slugs)} rule(s) by {args.reviewer} at {reviewed_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
