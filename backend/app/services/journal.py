import csv
import io
from uuid import UUID

from sqlalchemy import func, select

from app.models import Receipt
from app.runtime import Runtime
from app.schemas import CategoryTotal, DayTotal, MonthlySummary
from app.services.receipts import money, month_bounds

CSV_HEADER = [
    "date",
    "merchant",
    "tin",
    "receipt_number",
    "category",
    "vatable_sales",
    "vat_amount",
    "vat_exempt",
    "total",
    "status",
]


def safe_cell(value):
    if value is None:
        return ""
    value = str(value)
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


class JournalService:
    def __init__(self, runtime: Runtime):
        self.runtime = runtime

    def where(self, workspace_id: UUID, month: str):
        start, end = month_bounds(month)
        return (
            Receipt.workspace_id == workspace_id,
            Receipt.status == "verified",
            Receipt.receipt_date >= start,
            Receipt.receipt_date < end,
        )

    def months(self, workspace_id: UUID) -> list[str]:
        expression = func.to_char(Receipt.receipt_date, "YYYY-MM")
        with self.runtime.db.session() as session:
            return list(
                session.scalars(
                    select(expression)
                    .where(
                        Receipt.workspace_id == workspace_id,
                        Receipt.status == "verified",
                        Receipt.receipt_date.is_not(None),
                    )
                    .distinct()
                    .order_by(expression.desc())
                )
            )

    def summary(self, workspace_id: UUID, month: str) -> MonthlySummary:
        where = self.where(workspace_id, month)
        with self.runtime.db.session() as session:
            count, total, vat = session.execute(
                select(func.count(), func.sum(Receipt.total), func.sum(Receipt.vat_amount)).where(
                    *where
                )
            ).one()
            category = func.coalesce(Receipt.category, "Other")
            categories = session.execute(
                select(category, func.sum(Receipt.total), func.count())
                .where(*where)
                .group_by(category)
                .order_by(func.sum(Receipt.total).desc(), category)
            ).all()
            days = session.execute(
                select(Receipt.receipt_date, func.sum(Receipt.total))
                .where(*where)
                .group_by(Receipt.receipt_date)
                .order_by(Receipt.receipt_date)
            ).all()
        return MonthlySummary(
            month=month,
            total=money(total) or "0.00",
            vat_total=money(vat) or "0.00",
            count=count,
            by_category=[
                CategoryTotal(category=label, total=money(amount) or "0.00", count=count)
                for label, amount, count in categories
            ],
            by_day=[DayTotal(date=day, total=money(amount) or "0.00") for day, amount in days],
        )

    def export(self, workspace_id: UUID, month: str):
        where = self.where(workspace_id, month)

        def generate():
            buffer = io.StringIO(newline="")
            writer = csv.writer(buffer)
            writer.writerow(CSV_HEADER)
            yield buffer.getvalue()
            with self.runtime.db.session() as session:
                statement = (
                    select(Receipt)
                    .where(*where)
                    .order_by(Receipt.receipt_date, Receipt.id)
                    .execution_options(yield_per=100)
                )
                for row in session.scalars(statement):
                    buffer.seek(0)
                    buffer.truncate()
                    writer.writerow(
                        [
                            row.receipt_date.isoformat(),
                            safe_cell(row.merchant),
                            safe_cell(row.merchant_tin),
                            safe_cell(row.receipt_number),
                            safe_cell(row.category),
                            money(row.vatable_sales),
                            money(row.vat_amount),
                            money(row.vat_exempt),
                            money(row.total),
                            row.status,
                        ]
                    )
                    yield buffer.getvalue()

        return generate()
