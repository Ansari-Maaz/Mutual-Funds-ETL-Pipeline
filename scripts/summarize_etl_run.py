"""Summarize a completed ``app.cli run --all`` report for GitHub Actions."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def one_line(value: object, limit: int = 500) -> str:
    return " ".join(str(value).split())[:limit]


def main() -> int:
    report_path = Path("reports/latest_run.json")
    if not report_path.is_file():
        print("ETL run report is missing; the connector run did not finish.", file=sys.stderr)
        return 1

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read ETL run report: {exc}", file=sys.stderr)
        return 1

    results = report.get("results")
    if not isinstance(results, list):
        print("ETL run report does not contain a results list.", file=sys.stderr)
        return 1

    succeeded = [row for row in results if row.get("status") == "Succeeded"]
    failed = [row for row in results if row.get("status") == "Failed"]
    skipped = [row for row in results if row.get("status") == "Skipped"]
    lines = [
        "## Scheduled ETL connector summary",
        "",
        f"- Succeeded: **{len(succeeded)}**",
        f"- Failed: **{len(failed)}**",
        f"- Skipped: **{len(skipped)}**",
    ]
    if failed:
        lines.extend(["", "### Connector failures", ""])
        lines.extend(
            f"- `{one_line(row.get('source_id', 'unknown'), 100)}`: "
            f"{one_line(row.get('error', 'see job log'))}"
            for row in failed
        )
        for row in failed:
            print("::warning title=Connector failed::A source connector failed; see ETL summary and logs.")
    if skipped:
        lines.extend(["", "### Skipped connectors", ""])
        lines.extend(
            f"- `{one_line(row.get('source_id', 'unknown'), 100)}`: "
            f"{one_line(row.get('error', 'no details'))}"
            for row in skipped
        )

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("\n".join(lines) + "\n")
    print("\n".join(lines))

    if not succeeded:
        print("No connector succeeded; failing the ETL workflow.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
