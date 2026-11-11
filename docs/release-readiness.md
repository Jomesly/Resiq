# Release preparation — 11 November 2026

The code and deployment package address the production-audit findings. No site was published. Public release still requires running the documented host checks with real secrets, a domain, off-host backups and alerts. Real-photo accuracy remains unmeasured because no consented held-out dataset was supplied.

## Changes

- Shared database admission locking enforces workspace and global pending/receipt limits for both uploads and reprocessing. New workspaces cannot bypass the global limits. Queue scheduling, heartbeat comparisons and rate windows use PostgreSQL time.
- Recovery codes can be generated, downloaded, confirmed and replaced. Only hashes are stored on the server. Recovering a workspace or rotating browser access invalidates previous browser tokens. Production requires confirmed recovery before uploading. Switching workspaces clears browser query/page state.
- Receipt deletion atomically records durable cleanup work with the database deletion. Storage outages no longer leave an accessible database record with missing images. Maintenance retries cleanup, removes superseded attempts, and collects old orphan files while protecting current references and active attempts.
- API request/body limits, edge request/connection limits, private networks, bounded S3 timeouts, strict production settings, browser security headers and a non-root frontend image are included. Production API docs and the UI styleguide are disabled.
- Production Compose includes TLS routing, resource limits and maintenance. Private health checks cover worker, queue, maintenance, storage and free disk. Backup tooling stops writers for a consistent database/image snapshot; restoration checks use a separate temporary database and verify image references.
- Synthetic OCR regression thresholds now fail CI. A separate held-out dataset gate includes total and line-item accuracy. Bounded load checks report upload latency and completion failures. The frontend development dependency advisory was resolved with a scoped minimatch override, verified by lint and npm audit.

## Verification

Fresh verification passed 99 backend tests, Ruff checks/format, Alembic drift checks, frontend lint/typecheck, 15 frontend unit tests, and the production build. Two offline browser workflows and three connected real-Paddle/recovery workflows pass, including recovery after clearing browser storage. The optional private fuel-photo test is skipped when its local path is not configured.

A separate local deployment using `ENVIRONMENT=production`, generated private credentials, production network restrictions and resource limits started successfully. Recovery was enabled, a bundled photo was uploaded, and real Paddle OCR extracted the expected total. Operational status reported healthy. Nginx and Caddy configuration validation passed, and the production frontend image built successfully. No public certificate was requested.

The backup drill restored one processed synthetic receipt into a new isolated PostgreSQL container and verified all five referenced image files. The bounded load smoke completed eight receipts with two simultaneous upload clients, approximately 0.203-second upload p95 and 57.97 seconds total elapsed time, with zero recorded errors. This is a local smoke result, not a capacity guarantee for a future host.

The synthetic Tesseract gate passed 19/21 fields and all three totals. These are known synthetic fixtures and do not establish real-photo accuracy. npm audit reported zero vulnerabilities after the development dependency override; audits reflect the registry's information at the time run.

## Required at release time

Follow [deploy/README.md](../deploy/README.md). Verify DNS/TLS and routing on the chosen host; retain private secrets and immutable image tags; run the full workflow and recovery in staging; configure and verify off-host encrypted backups and alert delivery; run hosted CI and the load gate on the actual infrastructure. If choosing S3 instead of the provided shared local disk, verify the real provider's private bucket, read/write/delete permissions and backup/lifecycle settings.

Collect a representative consented held-out photo set before making an accuracy claim. Recovery-code access is implemented; email/password accounts and team roles are not. Losing both the browser credential and saved recovery code still loses access. Signed image links issued before token rotation may remain usable until their short expiry. No test suite can guarantee the absence of every future bug.
