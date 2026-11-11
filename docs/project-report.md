# Resiq project evaluation

Evaluation date: 11 November 2026. Status: integrated local MVP with independent review and regression fixes. No public deployment has been performed.

Follow-up: a user-supplied fuel receipt exposed missing support for `Php` amounts, VATable subtotal labels, following quantity rows and historical dates. These are corrected in extraction `rules-2`; 71 backend tests pass. A real OCR rerun of that image extracted VATable sales178.57, VAT21.43, exempt0.00 and total200.00, plus date2015-02-04 and quantity6.3291 at unit31.60. Old dates are preserved with a review warning. This is a single additional diagnostic example, not a revised accuracy benchmark. Stored readings require **Read again** to use the new rules.

## What is implemented

The complete upload → OCR → review/correct → save → journal → CSV workflow uses real FastAPI, PostgreSQL, image storage, and PaddleOCR. The existing Columnar Book frontend design is preserved. Own photos and bundled samples follow the same real processing path. Manual entry remains available after an unreadable image, and users can reprocess or delete receipts.

| Area | Implementation |
| --- | --- |
| Frontend | Next.js/React/TypeScript, multiple uploads, validation, queue states, source boxes, editable fields/items, live balance checks, responsive journal, search and filters |
| API | Thin FastAPI routes, service layer, typed request/response schemas, strict decimal-string validation, private anonymous workspaces |
| Persistence | PostgreSQL 16, SQLAlchemy 2, Alembic migration, indexed keyset pagination, SQL journal aggregates, streamed CSV |
| Vision | Actual file decoding, HEIC support, EXIF orientation, pixel limits, paper detection, perspective correction, small deskew, contrast enhancement, blur/darkness warnings |
| OCR | PaddleOCR 3.7 with PP-OCRv5 mobile detector and English recognizer; document orientation; optional Tesseract adapter |
| Extraction | Merchant/date/TIN/receipt number, total and VAT fields, item and quantity heuristics, category suggestion, confidence and original source evidence |
| Queue | PostgreSQL SKIP LOCKED claims, bounded attempts/backoff, lease recovery, unique ownership tokens, stale completion rejection, supervised warm child with timeout |
| Storage | Atomic local writes/shared Compose volume; S3-compatible adapter; expiring image signatures; workspace-scoped metadata access |
| Delivery | Docker API/worker images, Compose migration service, environment examples, dependency constraints, GitHub Actions checks and connected browser job |

The extraction record remains unchanged when a user edits the saved entry. Monetary storage/calculation uses Decimal and NUMERIC; JSON values are decimal strings. No OCR-derived amount is silently repaired to make arithmetic balance.

## Verification evidence

The current runs passed 56 backend tests, 14 frontend unit tests, frontend lint/typecheck/production build, two offline-demo browser flows, and two real connected browser flows. The backend suite uses real PostgreSQL with isolated per-test schemas. It covers workspace isolation, invalid uploads, signed URLs, pagination, money validation, verified-only journal/export, atomic rate limiting, quota cleanup, HEIC/EXIF/transparency handling, image bounds, extraction, competing queue claims, retries, stale completion after reclaim/deletion, and terminating a hung child.

The connected test ran against the production frontend and a real Paddle worker: renamed sample upload → extraction → correction → save → journal reload → CSV download → reprocess → delete. It checked widths 320, 375, 1024 and 1440 and ran axe on the review screen. Demo tests also scan the landing page and journal. After review fixes, both connected tests passed in 39.3 seconds, including normal upload/reprocessing and a sideways-photo regression. This is a smoke test, not a throughput benchmark.

The final rerun against the rebuilt API/Paddle containers passed both connected tests in 31.4 seconds. The final demo suite passed in 32.0 seconds. The evaluation server is currently available at http://localhost:3001 with the API at http://127.0.0.1:8000; the reproducible development instructions use frontend port 3000.

`alembic upgrade head` and `alembic check` succeeded against the local database. API and Paddle worker images built successfully; the containerized migration completed, API readiness passed, and both container dependency checks passed. The connected browser tests also passed against the containerized backend. CI has been configured but has not been run on a hosted GitHub runner in this session.

## OCR evaluation

The evaluation script processes pixels from **three bundled synthetic demo receipts**. These were available during implementation; this is not a held-out real-world dataset. Case-insensitive comparison covers seven header/money fields per receipt. It does not measure complete line-item accuracy or confidence calibration.

| Engine | Fields matching expected values | Kapihan | Mercury | Petron |
| --- | --- | --- | --- | --- |
| PaddleOCR | 20 / 21 | 10.478 s | 11.384 s | 8.862 s |
| Tesseract | 19 / 21 | 1.037 s | 0.643 s | 0.589 s |

Paddle startup with cached weights took 8.678 seconds on this Windows machine. All returned OCR boxes were within the image bounds. The source boxes were also inspected in the connected UI. The Kapihan fixture deliberately has a ₱145 printed total with ₱135 in items/VAT; the system correctly presents the discrepancy. See [Paddle results](../backend/eval/results-paddle.json), [Tesseract results](../backend/eval/results-tesseract.json), and [evaluation runner](../backend/eval/run.py) for exact observations, including mismatches.

## Scalability assessment

The architecture supports more API processes and more independent OCR workers without executing OCR inside web requests. PostgreSQL coordinates claims, and publication verifies the active lease under a row lock. Images use unique attempt paths, so a stale worker cannot overwrite the current image. Journal pages use bounded queries, summaries are aggregated in SQL, and exports stream records.

This is **prepared for modest scaling, not load-certified**. Each worker processes one image at a time and loads its own models. Size CPU/RAM and worker count using real measurements. Local files require a common volume; multi-host deployment needs private object storage. Each API/worker owns a bounded connection pool; total replicas must fit database connection capacity. Defaults limit each workspace to 1,000 receipts and 30 pending jobs. Anonymous workspace creation needs edge abuse controls for an internet-facing service.

## Remaining limitations

- No user accounts, workspace recovery, team roles, or cross-device synchronization. The browser's stored bearer token is the access credential. Losing it loses access; an invalid token is preserved rather than silently replaced.
- No held-out Philippine phone-photo dataset or measured accuracy target. Faded thermal paper, handwriting, unusual layouts, discounts, multi-line items, and merchant-specific tax formats may require corrections.
- A 12% VAT check is a consistency heuristic. This is not a tax filing service or a compliance certification.
- No production load test, hosted deployment, backup restoration drill, external object-store integration test, or hosted CI result is claimed.
- Reprocessing and interrupted blob writes can leave superseded attempt files. Receipt deletion removes the full prefix, but long-lived deployments need scheduled orphan cleanup and retention policies.
- PDF/multi-page documents and non-receipt document schemas are not implemented in this receipt-focused MVP.
- Infrastructure needs TLS, private production secrets, trusted proxy configuration, monitoring/alerts, storage lifecycle rules, database backups and appropriate access policies before public use.

## Independent review and decisions

A fresh read-only reviewer reported no Critical issues and four Important issues. Each Important finding was reproduced with a failing regression, then fixed: Read-stage overlays now use the actual oriented OCR image; amount normalization handles all accepted letter/sign forms; discount/savings footer labels cannot replace the payable total; and live validation clears obsolete machine warnings after correction. The full backend and frontend unit suites passed afterward.

Two minor findings remain explicit: the synthetic evaluation is report-only (no field-match CI threshold), and the confidence UI uses a single populated-value Check threshold below 0.7 rather than the planned separate low/very-low/missing chip states. Required fields and balance checks still validate current values.

Implementation decisions: keep the existing uncommitted frontend checkout; use sync PostgreSQL services and separate OCR processes; add lease tokens and execution deadlines; keep Paddle primary with an optional Tesseract engine; use verified-only journal totals/export; offer S3 for separate hosts; separate mock and real integration suites; pin a single compatible OpenCV wheel; restrict machine dates to the planned time window while allowing intentional manual historical dates; and provide a local evaluation without public deployment. These choices trade simpler local operation and safer review for a larger OCR image, slower real-OCR CI, and further work before public production use. Detailed decisions and evidence are in [the implementation ledger](implementation-ledger.md).

## Evaluation walkthrough

1. Follow the root README startup instructions and wait for `/readyz` to succeed.
2. Open the app and try Kapihan: verify the mismatch, inspect source boxes, correct the total, save and export November.
3. Upload a real phone photo with a different filename; review what was extracted and correct uncertain fields.
4. Reload the page to verify persistence; reprocess and delete a test receipt.
5. Try another browser profile to confirm that it has a separate workspace.

The strongest next improvement is a consented, representative receipt dataset with field-level ground truth, followed by extraction improvements driven by those failures. Account recovery and production operations should precede an unrestricted public launch.

