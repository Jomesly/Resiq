# Resiq UI Design: "The Columnar Book"

**Visual target (open in a browser):** `docs/design/mockups/ledger/index.html` (landing) and `docs/design/mockups/ledger/review.html` (review screen + its other states). The tokens live in `docs/design/mockups/ledger/tokens.css`.
**Inspiration, not source:** `docs/design/monad/` (user-supplied). What Resiq takes from it and what it deliberately leaves behind is listed in Section 8.
**Made with:** the Hallmark skill (custom direction, Floor + gates + `sloplint --render`), with ui-ux-pro-max guidance for forms, focus, tables and charts.
**Companion:** `2026-11-11-resiq-design.md` (product spec).

## 1. The idea

Every Philippine freelancer who registers with the BIR buys a **columnar book**: the green-ruled journal from National Book Store, kept in blue ballpen, with totals ruled off in red. Resiq is that book, filled in for you. **The resibo goes in, an entry comes out, and the total is ruled off only when it balances.**

The idea runs every decision:
- **Ground and rules** are ledger-pad stock: a pale green page with green hairline ruling, and columns separated by vertical rules.
- **Two inks, with meaning.** Values Resiq read are in **black** (ink). Values the user typed are in **ballpoint blue**, so you can always tell the machine's reading from yours. Blue is also the primary action and the current selection, and nothing else.
- **The closing rule is the signature.** A total gets the bookkeeper's **red double rule** only when its lines balance (VATable + VAT + exempt = total; items = subtotal). An unbalanced total has no rule and a plain-language note saying by how much it's off. Red appears nowhere else except errors.
- **Figures look like figures.** Everything that came off a receipt (amounts, TINs, OR numbers) is set in a mono, right-aligned, tabular. Nothing else is mono.

## 2. Tokens (copy `ledger/tokens.css` into `frontend/app/globals.css`)

| Role | Token | Value | Notes |
|---|---|---|---|
| Page | `--color-paper` | `oklch(96.5% 0.018 140)` | ledger-pad green, the canvas |
| Sheet (inputs, tables, panels) | `--color-paper-2` | `oklch(98.6% 0.008 140)` | |
| Band / hover | `--color-paper-3` | `oklch(92.5% 0.025 142)` | |
| Ink | `--color-ink` | `oklch(25% 0.03 160)` | 14.4:1 on paper |
| Secondary text | `--color-ink-2` | `oklch(40% 0.03 160)` | 8.2:1 |
| Muted text | `--color-muted` | `oklch(50% 0.025 160)` | 5.4:1, the smallest text colour |
| Ruling | `--color-rule` | `oklch(82% 0.05 150)` | hairlines and row rules only |
| Strong rule / control border | `--color-rule-strong` | `oklch(58% 0.08 152)` | 3.75:1, meets 1.4.11 for inputs |
| Ballpoint blue | `--color-accent` / `--color-focus` | `oklch(46% 0.17 262)` | 6.7:1; primary action, selection, user-written values, focus ring |
| Closing red | `--color-closing` (= `--color-error`) | `oklch(52% 0.19 27)` | the double rule and errors only |
| Lightbox | `--color-viewer` | `oklch(30% 0.025 160)` | behind receipt photos |
| State tints | `--color-tint-check / -ok / -error / -busy` | amber / green / red / blue at L90–92 | chip and banner fills, always with ink text (≥ 11.7:1) |
| OCR box | `--color-box`, `--color-box-active` | blue at 70% L / 18% alpha | |

**Type:** **Besley** (Clarendon-style serif, weight 500 only) for headings, legends and the wordmark. **Hanken Grotesk** 400/600 for all UI text. **Azeret Mono** 400/600 only for receipt-derived figures (amounts, TIN, OR no.). Three weights in running use. Load via `next/font/google`.
**Shape:** `--radius-control: 6px` for buttons, inputs and chips; `--radius-card: 6px`. Rectilinear, like a ledger: no pills. No card shadows; `--shadow-float` only for the floating receipt in the landing hero and for popovers.
**App type scale (1.125–1.2):** 13 / 14 / 16 / 18 / 22 / 28px. Landing uses the fluid display sizes in `tokens.css`.

## 3. Rules (also enforced by `sloplint`, see Task 23)

- Every colour and font goes through a token. Never `transition: all`; animate only `opacity`/`transform` (plus colour transitions).
- **No eyebrows, no tracked capitals, no uppercase labels, no mono labels.** Labels, table heads, chips and nav are Hanken in sentence case, one step smaller.
- No middle-dot meta strings ("Uploaded 11 November 2026, 9:41 am"), no arrows glued to links, no decorative status dots.
- One filled primary button style per screen (ballpoint blue). Secondary is outlined in `rule-strong`; destructive is a quiet red text button.
- Focus ring: 2px `--color-focus`, offset 2px, and `--color-viewer-ink` on the dark lightbox.
- `overflow-x: clip` on html/body. `prefers-reduced-motion` stops the skeleton pulse and the closing-rule fade.
- No invented metrics, testimonials or logos anywhere (sample data is labelled as sample).

## 4. Components (`frontend/components/resiq/`)

| Component | Spec |
|---|---|
| `Button` | `primary` / `secondary` / `quiet` (destructive) / `on-dark` (viewer toolbar). 40px app height, 48px landing. `white-space: nowrap`. All 8 states. |
| `Chip` | `check` (amber) "Needs review", "Check" · `ok` (green) "Balanced", "Verified", "Ready to save" · `error` (red) "Could not read", "Failed" · `busy` (blue) "Reading", "Suggested". Text always says the state. |
| `Field` | Label (with optional Chip) → input → `Read as …` small muted text → inline error, linked by `aria-describedby`. Edited inputs get `.is-edited` (blue text). |
| `MoneyInput` | Azeret Mono, right-aligned, `inputMode="decimal"`, normalises to 2 decimals on blur. |
| `AmountRows` | The ledger column: label left, MoneyInput right, hairline between rows. The total row has a 1px ink rule above, Besley label, larger input, and the `ClosingRule` below. |
| `ClosingRule` | Two 1px `--color-closing` lines 3px apart under the total column. Shown (opacity fade) only when `liveChecks` all pass. `aria-hidden`; the balance banner carries the meaning in text. |
| `BalanceBanner` | `role="status"`. Unbalanced: red tint, "**Does not balance by ₱10.00.** The lines add to ₱135.00; the total says ₱145.00." Balanced: green tint, "**Balanced.** VAT is 12% of VATable sales, and the lines add to the total." |
| `ReceiptViewer` | Dark lightbox panel. A stage segmented control (`role="tablist"`: As taken / Straightened / Read), `Show all text` toggle (`aria-pressed`), zoom − / + (labelled). The image + `<svg viewBox="0 0 {w} {h}">` overlay in processed-image pixels. Boxes: 3px `--color-box`; active/hover: blue stroke + `--color-box-active` fill. Boxes only on the "Read" stage. Quality warning as a translucent amber note. |
| `JournalTable` | Columnar table: vertical rules between columns, `rule-strong` under the head, figures in Azeret right-aligned, first column sticky on narrow screens, total row ruled off with `ClosingRule` cells. |
| `TopBar` | 56px. Besley wordmark, nav "Receipts" / "Journal" (current page = 2px blue underline), secondary "Upload receipts". |

## 5. Screens

### 5.1 Landing (`/`) (see `ledger/index.html`)
1. **Ruled header:** wordmark + one secondary action "Upload a receipt", hairline beneath.
2. **Hero (5/7 split, vertically centred in the first screen):** "From resibo to columnar book." / "Photograph a receipt. Resiq enters it and checks the VAT." / primary "Upload a receipt" + secondary "Try a sample receipt". On the right, the **product**: a tilted thermal receipt image whose TOTAL line connects (dashed blue curve) to a new **blue row** in a 3-column journal page (Date / Particulars / Amount) whose total is closed with the red double rule.
3. **"A crooked photo is straightened before it is read."** Four dark frames of the same receipt (as taken → paper found → squared → every line read), each with a Besley title and a one-line caption.
4. **"If the VAT does not add up, it stops and asks."** The arithmetic set large in Azeret (VATable, VAT, ruled sum, total as printed in red) + the red "Does not balance by ₱10.00" note.
5. **"November, ruled off the way the book is."** The full `JournalTable` (Date, Particulars, TIN, VATable, VAT, Amount) with the ruled total, plus a secondary "Download the sample CSV".
6. **"Black is what Resiq read. Blue is what you wrote."** Two example fields: the misread total with a Check chip, and the corrected one in blue with a Balanced chip.
7. **Footer:** "Your first receipt takes about ten seconds." + primary "Upload a receipt"; wordmark line and links.
- The hero's sample receipt is a **real image** (the mockup renders `ledger/src/receipt.html` to PNG), not HTML text. Ship the same: `public/samples/hero-receipt.png`.

### 5.2 Upload (inside `/` and as `/upload`)
The drop area is a `paper-2` sheet with a dashed `rule-strong` border and 6px radius; on drag-over the border goes solid blue and the fill `paper-3`. Each file gets a row: thumbnail, name, size (muted), a 2px blue progress line on a `rule` track (`role="progressbar"`), then a Chip that updates live, then an "Open" link.

### 5.3 Receipts (`/receipts`)
A `JournalTable` variant: thumbnail, Particulars (merchant, with OR no. in muted below), Date, Category, Amount, Status chip. Status filter as a segmented control, a month select, and search. Rows are links. Narrow screens: rows restack as two-line entries. Empty state: "No receipts yet." + primary "Upload a receipt". Loading: skeleton rows in the table's shape. Error: red-tint banner with "Try again".

### 5.4 Review (`/receipts/[id]`) (see `ledger/review.html`)
- TopBar → breadcrumb "Receipts / {merchant}" → grid `minmax(0,7fr) minmax(380px,5fr)`.
- **Left:** `ReceiptViewer` (sticky). **Right:** the entry panel (`paper-2`, rule border): status Chip, Besley merchant name (live), muted "Uploaded {date}, {time}", `BalanceBanner`, then fieldsets **Who and when** (Merchant, TIN, OR no., Date, Category with a "Suggested" chip), **Amounts** (`AmountRows` + `ClosingRule`), **Line items** (editable table + "Add a line"), then a sticky action bar: primary "Save to journal", secondary "Read again", quiet "Delete" (confirm dialog).
- Focus/hover on a field highlights its box. Clicking a box focuses its field.
- **The other states, drawn in the mockup:** *Reading* (step list Straighten → Read the lines → Fill the entry with the current step in blue, plus skeleton lines) · *Could not read* ("No text found in this photo", "Enter it by hand") · *Saved* ("Saved to November", "₱135.00 is now the ninth row of your journal", "Next receipt").
- Below 64rem: single column, viewer not sticky (360px stage).

### 5.5 Journal (`/journal`, formerly "dashboard")
Besley month title + month select. A three-cell summary row (Total spent, Receipts, VAT paid: label in muted Hanken, figure in Azeret 28px). **Spend by category:** horizontal bars in ink, sorted descending, direct value labels in Azeret, and a "Show as table" toggle. Then the month's `JournalTable` ruled off, and the primary "Export November as CSV".

## 6. Copy voice
The owner's own nouns: *resibo, columnar book, journal, OR no., VATable, rule off.* Sentence case everywhere. Money `₱1,250.00`. Dates "9 Nov 2026" in tables and "11 November 2026, 9:41 am" in meta. Buttons say what they do: "Save to journal", "Read again", "Enter it by hand". Errors say what happened and what to do next.

## 7. Accessibility
All text pairs above are ≥ 4.5:1 (computed). Control borders are 3.75:1. A visible focus ring on every control, including on the dark viewer. 44px touch targets on mobile. Labels are visible, never placeholder-only, and errors use `aria-describedby`. A failed save focuses an error summary. Status is always words. The chart has a table fallback. The receipt image alt reads "Receipt from {merchant}, {date}". Reduced motion is respected. No horizontal page scroll at 320px; wide tables scroll inside their own region with a sticky first column.

## 8. What came from the Monad reference, and what didn't
**Kept as inspiration:** a tinted canvas instead of white; a serif-for-headings / functional-face-for-UI split; hairline rules instead of shadows; a single saturated action colour (Monad's Lake Blue became ballpoint blue); a calm, spacious rhythm; the "pipeline" idea (now the four real processing passes and the viewer's stage control).
**Left behind on purpose:** parchment cream, pill buttons, monospace for all UI text, uppercase tracked labels, the pastel gradient washes, middle-dot strings, glyph status dots, and Instrument Serif. Resiq's identity comes from its own subject (the BIR columnar book and its two inks), not from Monad's.
