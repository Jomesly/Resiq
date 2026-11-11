import pytest

from app.extraction import extract, parse_amount
from app.schemas import OcrLine


def lines(*texts):
    return [
        OcrLine(text=t, confidence=0.95, box=(10, i * 30, 500, i * 30 + 20))
        for i, t in enumerate(texts)
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("P1,25O.00", "1250.00"),
        ("P145.0O", "145.00"),
        ("₱1 250.00", "1250.00"),
        ("12.345", None),
        ("TOTAL ITEMS 4", None),
        ("-12.50", "-12.50"),
    ],
)
def test_amounts(text, expected):
    assert parse_amount(text) == expected


def test_extract_fields_ignore_tender_and_preserve_evidence():
    result = extract(
        lines(
            "KAPIHAN SA KANTO",
            "TIN: 123-456-789-000",
            "OR No. 0004417",
            "11/09/2026",
            "Coffee 3 x 45.00 135.00",
            "VATable Sales 120.54",
            "VAT Amount 14.46",
            "TOTAL P135.00",
            "CASH 200.00",
            "CHANGE 65.00",
            "TOTAL ITEMS 3",
        ),
        "test",
    )
    assert result.merchant.value == "KAPIHAN SA KANTO"
    assert result.receipt_date.value == "2026-11-09"
    assert result.receipt_number.value == "0004417"
    assert result.total.value == "135.00"
    assert result.total.box == (10, 210, 500, 230)
    assert result.vatable_sales.value == "120.54"
    assert result.vat_amount.value == "14.46"
    assert result.line_items[0].quantity == "3"
    assert all(check.passed for check in result.checks)


def test_split_label_amount_rows_and_no_fabrication():
    result = extract(
        [
            OcrLine(text="TOTAL", confidence=0.9, box=(10, 100, 100, 120)),
            OcrLine(text="1,250.00", confidence=0.8, box=(300, 102, 450, 122)),
        ],
        "test",
    )
    assert result.total.value == "1250.00"
    assert result.receipt_date.value is None
    assert result.merchant.value is None
    assert extract([], "test").total.value is None


def test_invalid_date_and_mismatch_warn():
    result = extract(
        lines("SHOP", "02/30/2026", "VATable Sales 100.00", "VAT Amount 50.00", "TOTAL 150.00"),
        "test",
    )
    assert result.receipt_date.value is None
    assert not next(c for c in result.checks if c.name == "vat_math").passed


def test_quantity_on_preceding_row():
    result = extract(lines("COFFEE SHOP", "2 @ 45.00", "COFFEE 90.00", "TOTAL 90.00"), "test")
    assert result.line_items[0].quantity == "2"
    assert result.line_items[0].unit_price == "45.00"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("TOTAL 1,25i.00", "1251.00"), ("TOTAL 1,25L.00", "1251.00"), ("-P100.00", "-100.00")],
)
def test_all_accepted_money_glyphs_are_safe(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize("label", ["TOTAL DISCOUNT", "TOTAL SAVINGS", "TOTAL ITEMS", "TOTAL QTY"])
def test_footer_totals_cannot_replace_payable(label):
    result = extract(lines("SHOP", "TOTAL 1250.00", label + " 50.00"), "test")
    assert result.total.value == "1250.00"
