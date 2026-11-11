# Backend implementation ledger

Scope: complete the backend, connect the frontend, improve the structure, verify the whole project, and provide an evaluation report. Base commit: 5142ddc. Existing frontend work is uncommitted on feat/frontend.

## Decisions

- Follow the product spec and API contract, implementing the backend tasks in cohesive dependency groups. Keep the existing working checkout so the completed frontend is available; don't create a worktree from the docs-only commit.
- Postgres 16 is used locally and in tests. API endpoints use SQLAlchemy synchronous sessions in FastAPI's worker threads; CPU OCR runs in a separate supervised process.
- Add a lease ownership token and execution timeout to the planned SKIP LOCKED queue. A stale attempt cannot publish results after a retry, reprocess, or deletion.
- Keep PaddleOCR as the primary engine and expose a Tesseract adapter for lighter local use. Both process real pixels; fixture OCR is explicitly restricted to tests.
- Journal, summary, and journal CSV default to verified entries, matching the interface's promise that a receipt enters the book only after save. Add paginated journal and months endpoints to replace frontend N+1 detail requests.
- Local disk is shared by API and workers in Compose. S3-compatible storage is available for workers on separate hosts; disk storage alone is not a multi-host deployment.
- Existing frontend mock tests remain isolated from the real-backend integration tests.
- Collect build/test evidence and the final review in the project report; do not claim held-out real-receipt accuracy from synthetic samples.

## Progress

- Inspected the approved specs, frontend types, local tooling, and PaddleOCR 3.x documentation.
- Implemented and verified PostgreSQL persistence, workspace auth, signed image routes, upload validation, CRUD, paginated journal, SQL summaries, streaming CSV, migration and durable job claims.
- Implemented actual preprocessing, Paddle/Tesseract adapters, source-preserving extraction, arithmetic checks, date rules, supervised worker deadlines and completion fencing.
- Connected the frontend to the real API by default. Replaced journal N+1 detail requests with paginated entries and server aggregates. Scoped browser credentials by API base, and preserved invalid tokens on 401.
- Ruling: use one OpenCV contrib wheel pinned to Paddle's compatible version rather than simultaneously installing headless/contrib wheels — both own the cv2 import and can overwrite each other; costs a few GUI-linked system packages in the image.
- Ruling: retain isolated fake-only unit tests, but add a separate real Paddle connected browser test and synthetic pixel evaluation — fake-only end-to-end coverage cannot validate the integration; costs model downloads and CI runtime.
- Ruling: receipt dates extracted by the machine use the planned ten-year window and no future dates; explicitly entered dates remain user-controlled for historical corrections — avoids inventing machine dates without forbidding an intentional historical entry.
- Ruling: keep all work in the existing branch without publishing or deployment — user requested a build and evaluation report; production credentials/hosting are not configured.
- Verified: frontend lint/typecheck/build, 12 unit tests, 2 demo browser flows, 1 connected real Paddle browser workflow, 49 backend tests, Alembic upgrade/check. Final review and container verification are in progress.
- Recorded synthetic OCR results: Paddle20/21 selected fields, Tesseract19/21. Mercury merchant differs because full printed corporate name is preserved; Tesseract additionally misreads Petron VATable amount. No held-out accuracy claim.
- Final review: fresh read-only reviewer on gpt-6-astra identified four Important issues, no Critical issues. All four were reproduced with failing tests and fixed: processed-image overlay selection, accepted OCR glyph normalization, discount/savings total exclusion, and stale validation warnings after user correction.
- Final verification after fixes: 56 backend tests, 14 frontend unit tests, Ruff, frontend lint and production build, and Alembic drift check passed. Connected sideways-photo regression added.
- Final: minor (deferred): synthetic evaluation remains report-only; CI fails on execution errors but does not enforce a field-match baseline. This differs from the planned accuracy gate and avoids presenting three synthetic samples as a representative accuracy threshold.
- Final: minor (deferred): confidence UI retains its single populated-value Check threshold (<0.7); the planned separate <0.6/<0.3 and missing-value chip states are not implemented. Required fields are still validated and missing fields are listed in the live banner.
- Final: Ruling: public deployment/host behavior, held-out photo accuracy/throughput, accounts/recovery/teams, orphan cleanup, live S3, and hosted CI remain declared limitations. Local build, integration, container execution and reproducible checks satisfy this evaluation handoff; these unmeasured capabilities must not be advertised as production guarantees.
- Final container verification: rebuilt API/migration/Paddle images, migration success, /readyz healthy, no dependency conflicts; connected standard and sideways browser workflows passed against final containers in 31.4 seconds. Two demo browser flows passed in 32.0 seconds. Final source checks: 56 backend tests, 14 frontend unit tests, Ruff check/format, frontend lint/build/typecheck, Alembic check. No public deployment, push or hosted CI run.

## Real fuel receipt correction

- User's Petron photo exposed an extraction defect: OCR already read the amounts, but the currency matcher rejected the attached `Php` prefix. Added PHP/Php variants, signs and OCR digit normalization without matching currency fragments inside words.
- Tax labels now accept `Sub Total (12% Vatable)` and keep the VATable/exempt components distinct from a generic subtotal. Payable-label ranking includes `TOTAL AMOUNT TO BE PAID`.
- Adjacent quantity/price rows work before or after an item. Association requires close geometry and agreement with the printed item amount within 0.05; standalone quantity lines never become extra items or get reused.
- Ruling superseding the earlier ten-year cutoff: retain valid historical dates from 1900 through today, lower confidence and show an old-date warning beyond ten years. The user's readable 2015 receipt is valid evidence; silently discarding the date was misleading. Future/impossible dates remain rejected.
- Fuel category recognizes gasoline/petrol stations. Extraction version is now rules-2. Existing stored results need explicit reprocessing; user corrections are not overwritten automatically.
- Regression-first verification: 12 new/updated failures reproduced before fixes; full backend suite now passes 71 tests. Actual image re-run returned sales178.57/VAT21.43/exempt0.00/total200.00, date2015-02-04, receipt514700, quantity6.3291/unit31.60; all three arithmetic checks passed.
- Added optional private-image browser check using RESIQ_PETRON_TEST_IMAGE; the photo is not bundled into public assets.
- Final re-verification after the fuel-receipt fix (2026-11-11): backend 71 tests, Ruff check/format, Alembic check; frontend lint, typecheck, 14 unit tests, production build; demo browser suite 2/2; connected real-Paddle browser suite 3/3 (standard workflow, sideways photo, private fuel receipt via RESIQ_PETRON_TEST_IMAGE). The integration test's Category locator was made exact after the review screen added a "Focus Category" overlay button with the same label text.
