# Production release procedure

This package targets one Linux host with Docker Compose, a persistent disk, and a domain. It is prepared for deployment; nothing here publishes the app automatically. The frontend and API use the same HTTPS origin. Only Caddy exposes ports 80/443. PostgreSQL, API, workers, maintenance, and frontend have no public host ports.

## First release

1. Use a dedicated host with at least 4 CPU cores, 8 GiB RAM, and enough disk for receipts, database, Docker images, and backups. These are starting allocations, not a certified capacity claim. Keep SSH restricted and allow incoming HTTP/HTTPS for certificate issuance.
2. Point the domain to the host. From the repository root run `python deploy/generate-env.py --domain receipts.your-domain.com`. This creates `deploy/.env.production` with unique database, signing, and operations secrets. Keep an encrypted copy outside the host. Never commit this file, publish `docker compose config` output, or include it in logs.
3. Set a unique `RELEASE_TAG` in that file, such as the Git commit SHA. Keep the previous tag available. Check the release configuration without printing secrets:

   ```sh
   docker compose --env-file deploy/.env.production -f deploy/compose.production.yml config --quiet
   docker compose --env-file deploy/.env.production -f deploy/compose.production.yml build
   docker compose --env-file deploy/.env.production -f deploy/compose.production.yml up -d
   ```

4. Migrations must finish before API, workers, and maintenance start. Wait for `/readyz`, then create and save a recovery code, upload a photo, review/correct it, save to the journal, reload, export CSV, recover in a fresh browser, and delete the test receipt.
5. Run `deploy/monitor.sh`. It checks worker freshness, maintenance, storage read/write/delete, free disk, cleanup age, and queue age. Schedule it every five minutes and wire nonzero exit/output to your monitoring provider. Also monitor the public `/readyz` from outside the host and Docker restart/OOM events. These scripts provide signals; they do not deliver alerts without that integration.
6. Run the backup and restore drill below, copy the encrypted backup off-host, and verify retrieval before accepting important receipts.

Do not expose the development `docker-compose.yml` publicly. Production startup rejects the development database/signing credentials, insecure origins, disabled rate limits, and missing operations credentials. The release frontend build rejects a missing HTTPS API origin or demo mode. Public URL changes require a frontend rebuild. If the dedicated edge subnet conflicts with an existing network, set `EDGE_SUBNET` to a free private /24.

## Recoverable access

Workspace access is a high-entropy browser token, with a separate recovery code stored only as a hash on the server. Production requires a confirmed recovery code before upload. Users download/store the code, then confirm it; preparing a replacement does not invalidate their old saved code. Recovery and browser-key rotation revoke previous browser tokens. The recovery code remains usable until explicitly replaced, so a lost HTTP response does not strand the user. Already-issued image links can remain valid for up to 15 minutes.

This is recovery-code access, not email/password accounts or team permissions. A user who loses both browser access and their saved recovery code cannot be recovered by the app. Treat recovery files as credentials. They are never sent through email, analytics, or logs.

## Backups and restoration

For the supplied local-volume deployment:

```sh
python deploy/backup.py backup --env-file deploy/.env.production --output backups/release-YYYYMMDD-HHMM
python deploy/backup.py restore-check backups/release-YYYYMMDD-HHMM
```

Backup briefly stops API, workers, and maintenance, takes a PostgreSQL custom-format dump and a receipt-volume archive, writes SHA-256 checksums, and restarts only services that were running. Schedule a nightly backup during a maintenance window, plus one before every migration. Recovery point objective is the last successful off-host backup; actual restoration time must be measured on the chosen host. Keep daily copies for seven days and weekly copies for four weeks, adjusted to the product retention promise. Encrypt and copy the complete directory off-host, separately from the private environment file.

`restore-check` validates checksums, restores the dump into a new isolated PostgreSQL container, extracts the archive to a temporary directory, and verifies every referenced image. It never overwrites the live database. It removes its temporary container afterward. Allow sufficient RAM/disk for this drill; it uses a temporary PostgreSQL data filesystem. Verify restoration after upgrades and at least monthly.

For actual disaster recovery, create a **new** empty production deployment with the same private environment, restore `database.dump` using `pg_restore --no-owner --exit-on-error`, and restore the archive's `receipts/` contents into that deployment's receipts volume with ownership `10001:10001`. Keep API, workers, and maintenance stopped until both restores finish. Run migrations, start services, perform the workflow smoke test, then switch DNS/routing. Retain the old deployment until verification succeeds. Never use `alembic downgrade base` as rollback: it deletes receipt tables.

## Release and rollback

Take a verified backup first. Build a new immutable image tag, run migrations as the release job, then replace containers. Current migrations are additive: the previous app can run against the new schema. For an application-only rollback, restore the previous `RELEASE_TAG` and run `up -d --no-build`; do not run a database downgrade. Future incompatible schema changes require an explicit expand/contract plan or restore to a new deployment. Never run `down -v` on production.

## Limits and retention

Limits default to 1,000 workspaces, 10,000 receipts globally, 100 pending jobs globally, 1,000 receipts and 30 pending jobs per workspace. Upload and reprocessing share admission locks and limits across replicas. The edge rate-limits requests before forwarding bodies; the API also has atomic per-IP/global rate limits. Only Caddy is trusted by the gateway for the original client IP, and the API accepts forwarding headers only on its private network. Reassess limits using staging load measurements and available disk.

Maintenance retries persisted deletion tasks every five minutes. It removes superseded OCR attempts after replacement, and hourly removes unreferenced files older than 24 hours. Current receipt images and active OCR attempts are protected. User-requested receipt deletion removes database access immediately, with physical deletion retried if storage is unavailable. Backups retain deleted receipts until the backup expires. Saved receipts do not expire automatically; disclose this policy and backup retention to users before release. Monitor the global workspace cap; abandoned workspaces require operator review rather than automatic loss of recoverable access.

The supplied deployment uses a shared local volume. The S3 adapter has contract tests but still needs a real-provider staging roundtrip, bucket privacy checks, version-retention/lifecycle settings, and provider backup procedures if you choose that alternative. Do not reuse the local-volume backup instructions for S3.

## OCR and load gates

CI now fails on synthetic field/total regression or out-of-bounds source boxes. These are smoke fixtures, not proof of real-photo accuracy. From `backend/`:

```sh
python eval/run.py --engine paddle --output eval/results-release.json
python eval/load.py --url https://staging.your-domain.com --count 8 --concurrency 2
python eval/run.py --engine paddle --manifest eval/data/manifest.json --output eval/held-out-results.json
```

The bounded load check creates a disposable workspace, uploads up to 20 synthetic photos, waits for OCR, checks upload p95 and completion deadlines, and deletes its receipts. Run only against your own staging environment. It does not certify arbitrary concurrent load.

The held-out manifest requires at least 30 unique consented photos by default, 90% header-field accuracy, 95% total accuracy, 85% exact line-item-list accuracy, and valid source boxes. Freeze ground truth before tuning. Example shape (place image files beside the manifest, never in public assets):

```json
{"consented": true, "held_out": true, "receipts": [{"image": "photo-001.jpg", "fields": {"merchant": "Shop", "receipt_date": "2026-11-01", "total": "112.00"}, "line_items": [{"description": "Item", "quantity": "1", "unit_price": "112.00", "amount": "112.00"}]}]}
```

No held-out photos were supplied for this release preparation. That gate must be run before claiming real-world accuracy. Review/correction remains required. On the actual release host, also verify TLS, restore delivery, alerts, hosted CI, and measured load; local green tests do not replace those checks.
