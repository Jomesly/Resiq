"""Conservative, evidence-preserving Philippine receipt heuristics.

Missing fields stay missing. Arithmetic checks never silently repair OCR values.
All boxes refer to the exact image passed to the OCR adapter.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from app.dates import in_receipt_window, receipt_date, today_manila
from app.schemas import Check, Extraction, FieldValue, LineItemCandidate, OcrLine

AMOUNT = re.compile(
    r"(?<![\w.])(?:-\s*)?(?:PHP|P|₱)?\s*-?\s*\d[\d,OolI ]*\.[\dOoIl]{2}(?![\d.])", re.I
)
SUMMARY = re.compile(
    r"\b(total|subtotal|vat|vatable|exempt|cash|change|tender|payment|discount|amount due|balance|sales|tax)\b",
    re.I,
)
LABELS = {
    "vatable_sales": r"\b(?:vat\s*able(?:\s+sales)?|vat\s+sales)\b",
    "vat_exempt": r"\b(?:vat[ -]?)?exempt\b",
    "vat_amount": r"\b(?:vat\s*(?:amount|12\s*%)?|12\s*%\s*vat|tax)\b",
    "subtotal": r"\bsub[ -]?total\b",
    "total": r"\b(?:grand\s+total|total\s*(?:amount|due)?|amount\s*(?:due|payable)|balance\s*due)\b",
}


def parse_amount(text: str) -> str | None:
    matches = list(AMOUNT.finditer(text))
    if not matches:
        return None
    value = re.sub(r"PHP|[P₱,\s]", "", matches[-1].group(), flags=re.I)
    value = value.translate(
        str.maketrans(
            {
                "P": None,
                "p": None,
                "₱": None,
                "O": "0",
                "o": "0",
                "I": "1",
                "i": "1",
                "L": "1",
                "l": "1",
            }
        )
    )
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None
    return f"{amount:.2f}" if abs(amount) < Decimal("10000000000") else None


def group_rows(lines: list[OcrLine]) -> list[OcrLine]:
    rows: list[list[OcrLine]] = []
    for line in sorted(lines, key=lambda x: (x.box[1], x.box[0])):
        if not line.text.strip():
            continue
        for row in reversed(rows[-3:]):
            anchor = row[0].box
            overlap = min(anchor[3], line.box[3]) - max(anchor[1], line.box[1])
            if overlap > 0.5 * min(anchor[3] - anchor[1], line.box[3] - line.box[1]):
                row.append(line)
                break
        else:
            rows.append([line])
    return [
        OcrLine(
            text=" ".join(x.text for x in sorted(row, key=lambda x: x.box[0])),
            confidence=min(x.confidence for x in row),
            box=(
                min(x.box[0] for x in row),
                min(x.box[1] for x in row),
                max(x.box[2] for x in row),
                max(x.box[3] for x in row),
            ),
        )
        for row in rows
    ]


def evidence(value: str, row: OcrLine, confidence: float = 1) -> FieldValue:
    return FieldValue(
        value=value, confidence=round(row.confidence * confidence, 3), source=row.text, box=row.box
    )


def quantity_row(row: OcrLine) -> tuple[str, str] | None:
    """Recognize a standalone quantity @ price row without making it an item."""
    prefix = re.match(r"^\s*(\d{1,9}(?:\.\d{1,4})?)\s*[@xX]\s*", row.text)
    if not prefix or not AMOUNT.fullmatch(row.text[prefix.end() :].strip()):
        return None
    unit = parse_amount(row.text[prefix.end() :])
    return (prefix[1], unit) if unit is not None else None


def extract(lines: list[OcrLine], engine: str) -> Extraction:
    result = Extraction(engine_version=engine + "/rules-2")
    total_rank = -1
    rows = group_rows(lines)
    used_quantity_rows: set[int] = set()
    for index, row in enumerate(rows):
        text = row.text.strip()
        if (
            index < 5
            and result.merchant.value is None
            and len(text) <= 250
            and re.search(r"[a-z]{3}", text, re.I)
            and not re.search(
                r"\b(tin|vat|date|receipt|invoice|total|tel|address|cashier)\b", text, re.I
            )
            and parse_amount(text) is None
        ):
            result.merchant = evidence(text, row, 0.8)
        tin = re.search(
            r"\b(?:TIN|T\.I\.N\.?)\s*[:#]?\s*(\d{3}[ -]?\d{3}[ -]?\d{3}(?:[ -]?\d{3,5})?)",
            text,
            re.I,
        )
        if tin:
            result.merchant_tin = evidence(tin[1], row)
        number = re.search(
            r"\b(?:O\.?R\.?|SI|invoice|receipt)\s*(?:no\.?|number|#)\s*[:#]?\s*([A-Z0-9-]+)",
            text,
            re.I,
        )
        if number:
            result.receipt_number = evidence(number[1][:100], row)
        parsed = receipt_date(text)
        if parsed and result.receipt_date.value is None:
            result.receipt_date = evidence(parsed, row)
            if not in_receipt_window(date.fromisoformat(parsed), today_manila()):
                result.receipt_date.confidence = min(result.receipt_date.confidence, 0.55)
                result.warnings.append(
                    f"The printed date ({parsed}) is older than 10 years. Check the year before saving."
                )
        if quantity_row(row):
            continue
        amount = parse_amount(text)
        if amount is None:
            continue
        matched = False
        for field, pattern in LABELS.items():
            if re.search(pattern, text, re.I):
                if field == "total" and re.search(
                    r"\b(items?|qty|quantity|cash|change|tender|discount|savings|saved)\b",
                    text,
                    re.I,
                ):
                    continue
                if field == "total":
                    rank = (
                        2
                        if re.search(
                            r"\b(amount\s*(?:due|payable|to\s+be\s+paid)|grand\s*total|total\s*due|balance\s*due)\b",
                            text,
                            re.I,
                        )
                        else 1
                    )
                    if rank < total_rank:
                        matched = True
                        break
                    total_rank = rank
                setattr(result, field, evidence(amount, row))
                matched = True
                break
        if (
            matched
            or SUMMARY.search(text)
            or re.search(r"\b(TIN|date|time|no\.|telephone)\b", text, re.I)
        ):
            continue
        matches = list(AMOUNT.finditer(text))
        description = text[: matches[0].start()].strip(" -:")
        quantity = None
        qty = re.search(r"(\d{1,5}(?:\.\d{1,4})?)\s*[xX@]\s*$", description)
        if qty:
            quantity = qty[1]
            description = description[: qty.start()].strip()
        unit_price = parse_amount(matches[-2].group()) if len(matches) > 1 else None
        item_box = row.box
        if quantity is None:
            for neighbor_index in (index + 1, index - 1):
                if not 0 <= neighbor_index < len(rows) or neighbor_index in used_quantity_rows:
                    continue
                neighbor = rows[neighbor_index]
                candidate = quantity_row(neighbor)
                gap = max(row.box[1], neighbor.box[1]) - min(row.box[3], neighbor.box[3])
                if not candidate or gap >= 3 * max(
                    row.box[3] - row.box[1], neighbor.box[3] - neighbor.box[1]
                ):
                    continue
                if abs(Decimal(candidate[0]) * Decimal(candidate[1]) - Decimal(amount)) > Decimal(
                    ".05"
                ):
                    continue
                quantity, unit_price = candidate
                used_quantity_rows.add(neighbor_index)
                item_box = (
                    min(row.box[0], neighbor.box[0]),
                    min(row.box[1], neighbor.box[1]),
                    max(row.box[2], neighbor.box[2]),
                    max(row.box[3], neighbor.box[3]),
                )
                break
        if description and re.search("[a-z]", description, re.I) and len(result.line_items) < 500:
            result.line_items.append(
                LineItemCandidate(
                    description=description[:500],
                    quantity=quantity,
                    unit_price=unit_price,
                    amount=amount,
                    confidence=row.confidence * 0.8,
                    box=item_box,
                )
            )
    merchant = result.merchant.value or ""
    for category, pattern in [
        ("Food & Drinks", r"kapihan|cafe|coffee|restaurant|jollibee|mcdonald|food"),
        ("Health", r"pharmacy|mercury|drug|clinic"),
        ("Fuel", r"petron|shell|caltex|fuel|gasoline\s+station|petrol\s+station"),
        ("Groceries", r"grocery|supermarket|puregold"),
        ("Transport", r"grab|taxi|transport"),
        ("Utilities", r"meralco|water|internet"),
        ("Office Supplies", r"office|stationery|bookstore"),
    ]:
        if re.search(pattern, merchant, re.I):
            result.category = FieldValue(
                value=category, confidence=0.7, source=merchant, box=result.merchant.box
            )
            break

    def check(name, actual, expected, tolerance):
        result.checks.append(
            Check(
                name=name,
                passed=abs(actual - expected) <= Decimal(tolerance),
                detail=f"Expected {expected:.2f}; read {actual:.2f}.",
            )
        )

    if result.vatable_sales.value is not None and result.vat_amount.value is not None:
        check(
            "vat_math",
            Decimal(result.vat_amount.value),
            Decimal(result.vatable_sales.value) * Decimal(".12"),
            ".02",
        )
    if result.total.value is not None:
        total = Decimal(result.total.value)
        if result.line_items:
            check(
                "items_sum", sum(Decimal(item.amount) for item in result.line_items), total, ".05"
            )
        if result.vatable_sales.value is not None and result.vat_amount.value is not None:
            check(
                "subtotal_vat_total",
                total,
                Decimal(result.vatable_sales.value)
                + Decimal(result.vat_amount.value)
                + Decimal(result.vat_exempt.value or "0"),
                ".05",
            )
    for field in ("merchant", "receipt_date", "total"):
        if getattr(result, field).value is None:
            result.warnings.append(
                f"Could not identify {field.replace('_', ' ')}. Please enter it."
            )
    if any(not c.passed for c in result.checks):
        result.warnings.append("Some amounts do not reconcile. Check the photo before saving.")
    return result
