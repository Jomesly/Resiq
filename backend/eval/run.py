"""Report-only synthetic smoke evaluation, not a CI accuracy gate or held-out benchmark."""

import argparse
import json
import time
from pathlib import Path

from app.config import Settings
from app.vision.ocr import create_engine
from app.worker.pipeline import process


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=["paddle", "tesseract"], default="paddle")
    parser.add_argument("--output", type=Path, default=Path("eval/results.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    samples = json.loads((root / "frontend/lib/mock/samples.json").read_text())
    settings = Settings(ocr_engine=args.engine)
    started = time.perf_counter()
    engine = create_engine(settings)
    startup = time.perf_counter() - started
    results = []
    for sample in samples:
        start = time.perf_counter()
        result = process(
            (root / f"frontend/public/samples/{sample['key']}.png").read_bytes(), settings, engine
        )
        fields = {}
        for key, expected in sample["fields"].items():
            actual = getattr(result.extraction, key).value
            fields[key] = {
                "expected": expected["value"],
                "actual": actual,
                "matches": str(actual).casefold() == str(expected["value"]).casefold(),
            }
        results.append(
            {
                "sample": sample["key"],
                "seconds": round(time.perf_counter() - start, 3),
                "fields": fields,
                "items": len(result.extraction.line_items),
                "checks": [c.model_dump() for c in result.extraction.checks],
                "image_size": [result.width, result.height],
                "boxes_in_bounds": all(
                    0 <= line.box[0] <= line.box[2] <= result.width
                    and 0 <= line.box[1] <= line.box[3] <= result.height
                    for line in result.lines
                ),
            }
        )
    report = {
        "dataset": "Three bundled synthetic demo receipts; NOT a held-out real-photo benchmark",
        "engine": args.engine,
        "startup_seconds": round(startup, 3),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
