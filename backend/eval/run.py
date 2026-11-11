"""OCR regression gate, with a separate consented held-out dataset mode."""

import argparse
import json
import time
from pathlib import Path

from app.config import Settings
from app.vision.ocr import create_engine
from app.worker.pipeline import process


def gates(
    results, *, min_cases=3, min_fields=0.9, min_totals=0.95, min_items=0.85, require_items=False
):
    fields = [value["matches"] for row in results for value in row["fields"].values()]
    totals = [row["fields"]["total"]["matches"] for row in results if "total" in row["fields"]]
    items = [row["items_match"] for row in results if row.get("items_match") is not None]
    metrics = {
        "cases": len(results),
        "field_accuracy": sum(fields) / len(fields) if fields else 0,
        "total_accuracy": sum(totals) / len(totals) if totals else 0,
        "item_receipt_accuracy": sum(items) / len(items) if items else None,
    }
    failures = []
    if len(results) < min_cases:
        failures.append("insufficient_cases")
    if metrics["field_accuracy"] < min_fields:
        failures.append("field_accuracy")
    if len(totals) != len(results) or metrics["total_accuracy"] < min_totals:
        failures.append("total_accuracy")
    if not all(row["boxes_in_bounds"] for row in results):
        failures.append("source_boxes")
    if require_items and (
        len(items) != len(results) or metrics["item_receipt_accuracy"] < min_items
    ):
        failures.append("line_item_accuracy")
    return {"passed": not failures, "failures": failures, **metrics}


def load_cases(manifest: Path | None):
    root = Path(__file__).resolve().parents[2]
    if manifest is None:
        samples = json.loads((root / "frontend/lib/mock/samples.json").read_text())
        return [
            (
                root / f"frontend/public/samples/{sample['key']}.png",
                {k: v["value"] for k, v in sample["fields"].items()},
                None,
            )
            for sample in samples
        ]
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("consented") is not True or data.get("held_out") is not True:
        raise ValueError("Real-photo manifests must attest consented=true and held_out=true.")
    cases = []
    root = manifest.resolve().parent
    seen = set()
    for sample in data["receipts"]:
        image = (root / sample["image"]).resolve()
        if not image.is_relative_to(root) or image in seen or not image.is_file():
            raise ValueError(
                "Dataset images must be unique existing files inside the manifest directory."
            )
        seen.add(image)
        if "total" not in sample["fields"] or "line_items" not in sample:
            raise ValueError("Every held-out case needs total and line_items ground truth.")
        cases.append((image, sample["fields"], sample["line_items"]))
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=["paddle", "tesseract"], default="paddle")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("eval/results.json"))
    parser.add_argument("--min-cases", type=int)
    parser.add_argument("--min-field-accuracy", type=float, default=0.9)
    parser.add_argument("--min-total-accuracy", type=float, default=0.95)
    parser.add_argument("--min-item-accuracy", type=float, default=0.85)
    args = parser.parse_args()
    cases = load_cases(args.manifest)
    settings = Settings(ocr_engine=args.engine)
    started = time.perf_counter()
    engine = create_engine(settings)
    startup = time.perf_counter() - started
    results = []
    for index, (image, expected, expected_items) in enumerate(cases):
        start = time.perf_counter()
        result = process(image.read_bytes(), settings, engine)
        fields = {
            key: {
                "matches": str(getattr(result.extraction, key).value).strip().casefold()
                == str(value).strip().casefold()
            }
            for key, value in expected.items()
        }
        # Reports intentionally omit private OCR text, amounts, paths and expected values.
        actual_items = [
            {key: getattr(item, key) for key in ("description", "quantity", "unit_price", "amount")}
            for item in result.extraction.line_items
        ]
        results.append(
            {
                "case": index + 1,
                "seconds": round(time.perf_counter() - start, 3),
                "fields": fields,
                "items_match": actual_items == expected_items
                if expected_items is not None
                else None,
                "boxes_in_bounds": all(
                    0 <= line.box[0] <= line.box[2] <= result.width
                    and 0 <= line.box[1] <= line.box[3] <= result.height
                    for line in result.lines
                ),
            }
        )
    report = {
        "dataset": "held-out real photos"
        if args.manifest
        else "synthetic regression fixtures (not real-world accuracy)",
        "engine": args.engine,
        "startup_seconds": round(startup, 3),
        "results": results,
        "gate": gates(
            results,
            min_cases=args.min_cases or (30 if args.manifest else 3),
            min_fields=args.min_field_accuracy,
            min_totals=args.min_total_accuracy,
            min_items=args.min_item_accuracy,
            require_items=bool(args.manifest),
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"dataset": report["dataset"], "gate": report["gate"]}))
    return 0 if report["gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
