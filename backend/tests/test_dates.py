from datetime import date

import pytest

from app.dates import receipt_date


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("03/04/2025", "2025-03-04"),
        ("04-Mar-25", "2025-03-04"),
        ("March 4, 2025", "2025-03-04"),
        ("2026-11-12", None),
        ("11/10/2016", "2016-11-10"),
        ("2/4/2015", "2015-02-04"),
        ("2/4/1899", None),
        ("0917-123-4567", None),
        ("02/30/2026", None),
        ("2026-11-11", "2026-11-11"),
    ],
)
def test_receipt_dates(text, expected):
    assert receipt_date(text, today=date(2026, 11, 11)) == expected
