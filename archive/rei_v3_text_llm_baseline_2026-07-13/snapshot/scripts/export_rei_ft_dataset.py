from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.ft_dataset import dataset_path, export_dataset, validate_dataset, write_json


def resolve_dataset_path(value: str) -> Path:
    path = Path(value)
    if path.exists() or value.startswith(".") or "/" in value or "\\" in value:
        return path
    return dataset_path(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export approved REI fine-tune examples to SFT JSONL.")
    parser.add_argument("dataset", help="Dataset id or dataset directory.")
    args = parser.parse_args()

    dataset_dir = resolve_dataset_path(args.dataset)
    if not dataset_dir.exists():
        print(f"Dataset does not exist: {dataset_dir}")
        return 2

    validation = validate_dataset(dataset_dir)
    write_json(dataset_dir / "reports" / "validation_summary.json", validation)
    summary = export_dataset(dataset_dir)
    print(f"Exported approved valid examples to {summary['export_dir']}")
    for split, count in summary["counts"].items():
        print(f"{split}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
