from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.ft_dataset import dataset_path, validate_dataset, write_json


def resolve_dataset_path(value: str) -> Path:
    path = Path(value)
    if path.exists() or value.startswith(".") or "/" in value or "\\" in value:
        return path
    return dataset_path(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a REI fine-tune dataset.")
    parser.add_argument("dataset", help="Dataset id or dataset directory.")
    args = parser.parse_args()

    dataset_dir = resolve_dataset_path(args.dataset)
    if not dataset_dir.exists():
        print(f"Dataset does not exist: {dataset_dir}")
        return 2

    summary = validate_dataset(dataset_dir)
    report_path = dataset_dir / "reports" / "validation_summary.json"
    write_json(report_path, summary)
    print(
        "Validated "
        f"{summary['example_count']} examples: "
        f"{summary['valid_example_count']} valid, "
        f"{summary['invalid_example_count']} invalid, "
        f"{summary['approved_invalid_count']} approved-invalid."
    )
    print(f"Report: {report_path}")
    return 1 if summary["approved_invalid_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
