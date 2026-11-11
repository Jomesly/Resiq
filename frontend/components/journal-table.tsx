import Link from "next/link";
import { formatDate } from "@/lib/format";
import { formatAmount, sumMoney } from "@/lib/money";
import type { ReceiptDetail } from "@/lib/types";

type JournalRow = Pick<ReceiptDetail, "id" | "receipt_date" | "merchant" | "merchant_tin" | "receipt_number" | "vatable_sales" | "vat_amount" | "total">;

export function JournalTable({ rows, label, sample = false, partial = false }: { rows: JournalRow[]; label: string; sample?: boolean; partial?: boolean }) {
  const sum = (field: "vatable_sales" | "vat_amount" | "total") => formatAmount(sumMoney(rows.map((row) => row[field])));
  return <div className="journal-table" role="region" aria-label={label} tabIndex={0}>
    <table>
      <caption className="visually-hidden">{label}</caption>
      <thead><tr>
        <th scope="col">Date</th><th scope="col">Particulars</th><th scope="col">TIN</th>
        {!sample && <th scope="col">OR no.</th>}
        <th scope="col">VATable</th><th scope="col">VAT</th><th scope="col">Amount</th>
      </tr></thead>
      <tbody>{rows.map((row) => <tr key={row.id}>
        <td>{formatDate(row.receipt_date)}</td>
        <td>{sample ? row.merchant : <Link className="link" href={"/receipts/" + row.id}>{row.merchant ?? "Untitled receipt"}</Link>}</td>
        <td className="num">{row.merchant_tin ?? "—"}</td>
        {!sample && <td className="num">{row.receipt_number ?? "—"}</td>}
        <td className="num">{formatAmount(row.vatable_sales)}</td><td className="num">{formatAmount(row.vat_amount)}</td><td className="num">{formatAmount(row.total)}</td>
      </tr>)}</tbody>
      <tfoot><tr>
        <th scope="row" colSpan={sample ? 3 : 4}>{partial ? "Loaded entries" : "Total"}</th>
        <td className="num">{sum("vatable_sales")}</td><td className="num">{sum("vat_amount")}</td><td className="num">{sum("total")}</td>
      </tr></tfoot>
    </table>
  </div>;
}
