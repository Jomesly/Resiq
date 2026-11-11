# Resiq frontend

Resiq turns Philippine receipts into entries in a monthly expense journal. This Next.js app includes the landing page, multi-photo upload, receipts inbox, review screen, and journal.

## Run locally

From the repository root:

```sh
cd frontend
npm ci
npm run dev
```

Open [localhost:3000](http://localhost:3000). Choose **Try a sample receipt**, then change the Kapihan sa Kanto total from **145.00** to **135.00**. The VAT and line item checks clear, the red double rule appears, and **Save to journal** adds the entry to November. Open the journal to check category totals or download the CSV. The upload page also offers Mercury Drug and Petron Katipunan samples.

Normal development connects to `http://127.0.0.1:8000` for real OCR. Start the API and worker using the [root instructions](../README.md). JPG, PNG, WebP, and HEIC photos up to 10 MB are supported. Set `NEXT_PUBLIC_API_URL` in `.env.local` for another API, then restart or rebuild Next.js. The journal, aggregates, and CSV use verified receipts only; the journal uses paginated server queries.

The separate offline demo requires `NEXT_PUBLIC_DEMO_MODE=true`. It simulates reading bundled samples, stores photos in this browser, and allows manual entry of other uploads. It does not call the backend.

The [UI specification](../docs/superpowers/specs/2026-11-11-resiq-ui-design.md) describes the Columnar Book design. Visit `/styleguide` to see its controls and receipt states.

## Verify

```sh
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium --only-shell
npm run test:e2e
```

The standard browser tests start demo mode explicitly. They cover source boxes, balance correction, CSV download, and manual entry/deletion on a narrow viewport. The desktop flow scans the landing page, review screen, and journal with axe. Stop any server on port 3000 before running them. The separate `playwright.integration.config.ts` runs against the real API and OCR worker; see the root README for setup.
