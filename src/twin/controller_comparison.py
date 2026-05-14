"""Helpers for combining controller-comparison experiment summaries."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def load_summary_rows(csv_paths: list[Path]) -> list[dict[str, str]]:
    """Load and concatenate summary CSV rows from multiple controller runs."""

    rows: list[dict[str, str]] = []
    for csv_path in csv_paths:
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                rows.append(row)
    return sorted(
        rows,
        key=lambda row: (
            row.get("controller_app", ""),
            row.get("topology_name", ""),
            row.get("scenario_name", ""),
            row.get("background_traffic", ""),
            row.get("target_link", ""),
        ),
    )


def write_combined_summary(rows: list[dict[str, str]], csv_path: Path, json_path: Path) -> tuple[Path, Path]:
    """Write combined controller-comparison summaries to CSV and JSON."""

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path, json_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args for controller summary combination."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, nargs="+", required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for controller summary combination."""

    args = parse_args(argv)
    rows = load_summary_rows(args.inputs)
    csv_path, json_path = write_combined_summary(rows, args.output_csv, args.output_json)
    print(
        json.dumps(
            {
                "output_csv": str(csv_path),
                "output_json": str(json_path),
                "rows": len(rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
