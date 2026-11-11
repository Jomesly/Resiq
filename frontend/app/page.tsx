import Image from "next/image";
import Link from "next/link";
import { LandingHero } from "@/components/landing-hero";
import { JournalTable } from "@/components/journal-table";
import { ButtonLink, Chip } from "@/components/resiq/ui";

const passes = [
  ["The photo as taken", "Tilted, shadowed, with the table behind it.", "raw"],
  ["The paper found", "Its four corners located against the background.", "found"],
  ["Squared and evened", "Flattened to a rectangle, contrast lifted.", "square"],
  ["Every line read", "Each line boxed, so every field can show where it came from.", "read"],
];
const sampleRows = [
  { id: "petron", receipt_date: "2026-11-02", merchant: "Petron Katipunan", merchant_tin: "000-111-222-000", receipt_number: "120-55", vatable_sales: "1785.71", vat_amount: "214.29", total: "2000.00" },
  { id: "mercury", receipt_date: "2026-11-04", merchant: "Mercury Drug", merchant_tin: "000-333-444-000", receipt_number: "88120", vatable_sales: "547.10", vat_amount: "65.65", total: "612.75" },
  { id: "kapihan", receipt_date: "2026-11-09", merchant: "Kapihan sa Kanto", merchant_tin: "000-482-117-000", receipt_number: "0004417", vatable_sales: "120.54", vat_amount: "14.46", total: "135.00" },
];

export default function Home() {
  return <div className="landing">
    <header className="container"><nav className="nav" aria-label="Main">
      <Link className="wordmark" href="/">Resiq</Link>
      <div className="landing-nav-actions"><Link className="link" href="/receipts">Receipts</Link><ButtonLink href="/upload">Upload a receipt</ButtonLink></div>
    </nav></header>

    <main id="main">
      <LandingHero />
      <section className="container section" id="passes" aria-labelledby="passes-title">
        <div className="section__head">
          <h2 id="passes-title">A crooked photo is straightened before it is read.</h2>
          <p>See how a tilted, dim phone photo becomes a set of lines you can check against the original.</p>
        </div>
        <ol className="passes">{passes.map(([title, caption, stage]) => <li key={stage}>
          <figure className="pass">
            <div className="pass__frame" aria-hidden="true"><div className={"pass-photo pass-photo--" + stage}>
              <Image unoptimized src="/samples/hero-receipt.png" alt="" width={536} height={736} />
              {stage === "read" && <svg viewBox="0 0 536 736"><rect x="28" y="40" width="480" height="32" /><rect x="28" y="184" width="480" height="32" /><rect x="28" y="292" width="480" height="32" /><rect x="28" y="472" width="480" height="32" /></svg>}
            </div></div>
            <figcaption><h3>{title}</h3><p>{caption}</p></figcaption>
          </figure>
        </li>)}</ol>
      </section>
      <section className="container section balance" aria-labelledby="balance-title">
        <div><h2 id="balance-title">If the VAT does not add up, it stops and asks.</h2>
          <p className="balance__note">Its lines add to ₱135.00. The total was read as ₱145.00. Nothing is ruled off until you choose.</p></div>
        <div><dl className="sum">
          <dt>VATable sales</dt><dd>120.54</dd>
          <dt>VAT at 12%</dt><dd>14.46</dd>
          <dt className="ruled">Adds up to</dt><dd className="ruled">135.00</dd>
          <dt className="off">Total as read</dt><dd className="off">145.00</dd>
        </dl><p className="verdict">Does not balance by ₱10.00. Check the total or the items.</p></div>
      </section>
      <section className="container section" id="journal-example" aria-labelledby="journal-title">
        <div className="section__head"><h2 id="journal-title">November, ruled off the way the book is.</h2></div>
        <JournalTable rows={sampleRows} label="Sample November journal" sample />
        <div className="journal__foot"><p>Sample journal, November 2026</p><a className="btn btn--secondary" href="/samples/resiq-sample.csv" download>Download the sample CSV</a></div>
      </section>
      <section className="container section inks" aria-labelledby="inks-title">
        <div><h2 id="inks-title">Black is what Resiq read. Blue is what you wrote.</h2>
          <div className="inks__copy"><p>Any field it is unsure of is marked Check, with the text it saw underneath.</p>
            <p>Your corrections stay in blue, so you can always tell the machine’s reading from yours. Nothing reaches the journal until you save.</p></div>
        </div>
        <div className="field-demo">
          <div className="field"><label htmlFor="demo-misread">Total <Chip tone="check">Check</Chip></label>
            <input id="demo-misread" value="145.00" aria-describedby="demo-misread-note" readOnly /><small id="demo-misread-note">Read as P145.0O</small></div>
          <div className="field"><label htmlFor="demo-corrected">Total <Chip tone="ok">Balanced</Chip></label>
            <input id="demo-corrected" className="is-edited" value="135.00" aria-describedby="demo-corrected-note" readOnly /><small id="demo-corrected-note">Corrected by you</small></div>
        </div>
      </section>
    </main>
    <footer className="container footer">
      <h2>Put your first receipt in the book.</h2>
      <ButtonLink variant="primary" href="/upload">Upload a receipt</ButtonLink>
      <div className="footer__meta"><p>Resiq, made for Philippine freelancers who keep their own books.</p>
        <nav aria-label="Footer"><a className="link" href="#passes">How it reads</a><Link className="link" href="/journal">The journal</Link></nav></div>
    </footer>
  </div>;
}
