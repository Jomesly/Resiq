import re
from datetime import date, datetime
from zoneinfo import ZoneInfo


def today_manila() -> date:
    return datetime.now(ZoneInfo("Asia/Manila")).date()


def in_receipt_window(value: date, today: date) -> bool:
    try:
        oldest = today.replace(year=today.year - 10)
    except ValueError:
        oldest = today.replace(year=today.year - 10, day=28)
    return oldest <= value <= today


def receipt_date(text: str, *, today: date | None = None) -> str | None:
    today = today or today_manila()
    formats = [
        (r"(?<![\d-])\d{4}-\d{2}-\d{2}(?![\d-])", ["%Y-%m-%d"]),
        (
            r"(?<![\d/-])\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}(?![\d/-])",
            ["%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y"],
        ),
        (r"\b\d{1,2}-[A-Za-z]{3,9}-\d{2,4}\b", ["%d-%b-%y", "%d-%b-%Y", "%d-%B-%Y"]),
        (r"\b[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}\b", ["%b %d %Y", "%B %d %Y"]),
    ]
    for pattern, candidates in formats:
        for match in re.finditer(pattern, text):
            for fmt in candidates:
                try:
                    parsed = datetime.strptime(match[0].replace(",", ""), fmt).date()
                    # Age is a review warning, not a reason to erase readable evidence.
                    if date(1900, 1, 1) <= parsed <= today:
                        return parsed.isoformat()
                except ValueError:
                    pass
    return None
