import type { Metadata } from "next";
import { Button, Chip, ClosingRule, Skeleton, StatusChip, TopBar } from "@/components/resiq/ui";

export const metadata: Metadata = { title: "Styleguide" };

export default function Styleguide() {
  return <><TopBar /><main id="main" className="app-container screen styleguide">
    <div className="screen-heading"><div><h1>The Columnar Book</h1><p>Resiq’s type, controls and receipt states.</p></div></div>
    <section><h2>Actions</h2><div className="button-group">
      <Button variant="primary">Save to journal</Button><Button>Read again</Button>
      <Button variant="quiet">Delete</Button><Button disabled>Unavailable</Button>
      <Button aria-busy="true" disabled>Saving…</Button>
    </div></section>
    <section><h2>Receipt states</h2><div className="button-group">
      <StatusChip status="queued" /><StatusChip status="processing" /><StatusChip status="needs_review" />
      <StatusChip status="verified" /><StatusChip status="failed" />
    </div></section>
    <section><h2>Receipt figures</h2>
      <div className="field"><label htmlFor="style-total">Total <Chip tone="ok">Balanced</Chip></label>
        <input className="fig is-edited" id="style-total" value="135.00" readOnly />
      </div>
      <div className="closing-row"><ClosingRule /></div>
    </section>
    <section><h2>Reading</h2><Skeleton label="Reading a receipt…" /></section>
  </main></>;
}
