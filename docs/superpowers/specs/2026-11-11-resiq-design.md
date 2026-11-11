# Resiq: Receipt Intelligence for PH Freelancers and Small Businesses (Design)

## Intent

Resiq is a portfolio project you can demo in an interview. A user drops in a phone photo of a receipt. Resiq cleans up the image, reads it, and fills in a structured record: merchant, TIN, OR/SI number, date, VAT breakdown, total, and line items. The user checks the record on a review screen and fixes anything it got wrong. The audience is Philippine freelancers and small businesses who keep receipts for BIR filing and expense tracking.

The project should show engineering judgment, not just API calls. Four parts carry that:
1. A real image preprocessing pipeline that handles blur, skew, perspective, and lighting.
2. A rules-and-heuristics extractor whose output carries per-field confidence and cross-checks (VAT math, items vs. total).
3. A correction UX that treats the machine output as a draft.
4. An evaluation harness that reports field accuracy as a number.

## The 2-minute demo (the success test)

1. Open the deployed URL and click "Try with sample receipts", or drop your own photo.
2. The receipt card goes from *Queued* to *Processing* to *Needs review* within about 10 s.
3. Open the review screen. The photo sits on the left with OCR boxes over it. The extracted fields sit on the right, and low-confidence fields are highlighted. Clicking a field highlights where it came from in the photo.
4. Toggle the "Pipeline" view: original → document detected → warped/deskewed → enhanced.
5. Fix one misread total. The VAT/items mismatch warning clears. Save, and the record is *Verified*.
6. Open the dashboard: monthly spend by category, then export CSV with BIR-relevant columns (TIN, OR no., VATable sales, VAT).
7. The README shows a field accuracy table (merchant/date/total) on a held-out set.

## Goals

- Upload JPEG/PNG/WebP/HEIC up to 10 MB, one or many at a time.
- Asynchronous processing with visible status, retries, and a clear failure state.
- Extract: merchant, merchant TIN, receipt/OR/SI number, date, subtotal, VATable sales, VAT amount, VAT-exempt sales, total, line items (description, qty, unit price, amount).
- Every extracted field carries `confidence` (0–1), the source OCR text, and a bounding box.
- Review/edit screen. Saving records the user's final values. The machine extraction is kept unchanged so corrections can be measured.
- List, filter (status, month, text), delete, reprocess, CSV export, monthly category summary.
- Evaluation script with per-field accuracy. CI fails if accuracy on fixtures drops.
- Dockerized. Backend on Railway, frontend on Vercel, CI on GitHub Actions.

## Non-goals (v1)

- User accounts, passwords, OAuth. (Anonymous workspace token instead; see Constraints.)
- PDF and multi-page documents. Non-receipt document types (invoices, IDs).
- Multi-currency. Everything is PHP.
- Mobile app. The web app should still work in a phone browser for upload.
- LLM/vision-API extraction. It would defeat the "show engineering judgment" point.
- LayoutLM fine-tuning. That's a separate stretch plan after v1 ships and the eval harness exists to compare against.

## Anti-goals (failures even if it "works")

- A demo that hangs on "Processing" or a cold start of 30 s+.
- Silently wrong numbers shown as if certain. Low confidence must be visible.
- Losing the user's edits, or reprocessing that overwrites a verified record without asking.
- An accuracy claim in the README that no script can reproduce.

## Constraints

- Monorepo: `backend/` (Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Postgres 16), `frontend/` (Next.js App Router, TypeScript, Tailwind, shadcn/ui, TanStack Query).
- OCR: PaddleOCR 3.x (mobile det/rec models, English), behind an `OcrEngine` interface. Tests use a fake engine, so CI never needs Paddle.
- Image processing: OpenCV + Pillow (+ pillow-heif).
- No Redis/Celery: the job queue is a Postgres table using `SELECT … FOR UPDATE SKIP LOCKED` with a lease.
- Auth: `POST /api/workspaces` returns a random bearer token. The browser stores it in localStorage. Every API call is scoped to that workspace. Images are served via HMAC-signed, expiring URLs because `<img>` cannot send headers.
- Money is `Decimal`/`NUMERIC(12,2)` everywhere. It is a string in JSON, never a float.
- PH conventions: numeric dates are read MM/DD/YYYY. TIN format is `###-###-###(-###…)`. VAT is 12%.
- Deploy target needs ≥2 GB RAM for Paddle (Railway, not Render free tier). OCR models are baked into the Docker image at build time.

## Decided by the builder (Claude's calls; user said "you decide")

- Stack details above, PaddleOCR over Tesseract, rules over ML for v1, Postgres-as-queue, anonymous workspace tokens, Railway over Render.
- Datasets: SROIE (ICDAR 2019, Malaysian receipts, close to PH format) for eval, plus ~30 self-collected PH receipts (Jollibee, 7-Eleven, Mercury Drug, SM, Grab printouts) labeled by hand.
- Categories: fixed list (Food & Drinks, Groceries, Transport, Fuel, Utilities, Office Supplies, Health, Other). Merchant-keyword rules assign a category, and the user can change it.

## UI

The visual system is defined in `2026-11-11-resiq-ui-design.md`: an original "columnar book" direction, inspired by (not copied from) the user-supplied Monad reference in `docs/design/monad/`. The visual targets are `docs/design/mockups/ledger/index.html` and `ledger/review.html`. In the demo script, "dashboard" means the Journal page (`/journal`).

## Left to the implementer

Exact copy text beyond the UI spec's voice rules, and logging format.
