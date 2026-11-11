"""Bounded upload/OCR load smoke. Run only against your own staging instance."""

import argparse
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--image", type=Path, default=Path("../frontend/public/samples/kapihan.png")
    )
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--deadline", type=int, default=300)
    parser.add_argument("--max-upload-p95", type=float, default=5)
    parser.add_argument("--output", type=Path, default=Path("eval/load-results.json"))
    args = parser.parse_args()
    if not 1 <= args.count <= 20 or not 1 <= args.concurrency <= 8:
        parser.error("Use 1-20 receipts and 1-8 concurrent uploads.")
    ids, latencies, errors = [], [], []
    started = time.monotonic()
    with httpx.Client(base_url=args.url, timeout=30) as client:
        response = client.post("/api/workspaces")
        response.raise_for_status()
        client.headers["authorization"] = "Bearer " + response.json()["token"]
        recovery = client.post("/api/workspace/recovery")
        recovery.raise_for_status()
        client.post("/api/workspace/recovery/confirm", json=recovery.json()).raise_for_status()
        data = args.image.read_bytes()

        def upload(_):
            start = time.monotonic()
            response = client.post("/api/receipts", files={"file": ("load-photo.png", data)})
            response.raise_for_status()
            return response.json()["id"], time.monotonic() - start

        try:
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                futures = [pool.submit(upload, i) for i in range(args.count)]
                for future in futures:
                    try:
                        rid, seconds = future.result()
                        ids.append(rid)
                        latencies.append(seconds)
                    except Exception as exc:
                        errors.append(type(exc).__name__)
            waiting = set(ids)
            while waiting and time.monotonic() - started < args.deadline:
                for rid in list(waiting):
                    response = client.get(f"/api/receipts/{rid}")
                    response.raise_for_status()
                    state = response.json()["status"]
                    if state in ("needs_review", "verified", "failed"):
                        waiting.remove(rid)
                        if state == "failed":
                            errors.append("ocr_failed")
                if waiting:
                    time.sleep(2)
            if waiting:
                errors.append("deadline_exceeded")
            p95 = (
                sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)]
                if latencies
                else None
            )
            if p95 is not None and p95 > args.max_upload_p95:
                errors.append("upload_p95_exceeded")
            report = {
                "passed": not errors,
                "uploaded": len(ids),
                "completed": len(ids) - len(waiting),
                "concurrency": args.concurrency,
                "upload_p95_seconds": p95,
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "errors": errors,
                "scope": "bounded synthetic load smoke; not production capacity certification",
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report))
            return 0 if report["passed"] else 1
        finally:
            for rid in ids:
                client.delete(f"/api/receipts/{rid}")


if __name__ == "__main__":
    raise SystemExit(main())
