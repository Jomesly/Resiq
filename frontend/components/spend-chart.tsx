"use client";

import { useState } from "react";
import { formatPeso, toCents } from "@/lib/money";
import type { MonthlySummary } from "@/lib/types";
import { Button } from "./resiq/ui";

export function SpendChart({ categories }: { categories: MonthlySummary["by_category"] }) {
  const [table, setTable] = useState(false);
  const max = Math.max(1, ...categories.map(({ total }) => Math.abs(toCents(total) ?? 0)));
  return <section className="spend-section" aria-labelledby="spend-title">
    <div className="section-toolbar"><h2 id="spend-title">Spend by category</h2><Button aria-pressed={table} onClick={() => setTable((value) => !value)}>{table ? "Show as chart" : "Show as table"}</Button></div>
    {table ? <table className="spend-table"><caption className="visually-hidden">Spend by category</caption>
      <thead><tr><th scope="col">Category</th><th scope="col">Receipts</th><th scope="col">Amount</th></tr></thead>
      <tbody>{categories.map(({ category, count, total }) => <tr key={category}><th scope="row">{category}</th><td>{count}</td><td className="num">{formatPeso(total)}</td></tr>)}</tbody>
    </table> : <ul className="spend-bars" aria-label="Spending totals by category">{categories.map(({ category, total }) => {
      const cents = toCents(total) ?? 0;
      return <li key={category}><span>{category}</span>
        <span className="bar-track" aria-hidden="true"><span className={cents < 0 ? "is-credit" : ""} style={{ width: 100 * Math.abs(cents) / max + "%" }} /></span>
        <span className="fig">{formatPeso(total)}</span></li>;
    })}</ul>}
  </section>;
}
