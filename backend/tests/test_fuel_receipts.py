import pytest

from app.extraction import extract, parse_amount
from app.schemas import OcrLine


def rows(*texts):
    return [
        OcrLine(text=text, confidence=0.96, box=(10, 30 * i, 620, 30 * i + 22))
        for i, text in enumerate(texts)
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Php200.00", "200.00"),
        ("PHP 1,250.00", "1250.00"),
        ("php178.57", "178.57"),
        ("Php0.00", "0.00"),
        ("PHP-200.00", "-200.00"),
        ("-Php 200.00", "-200.00"),
        ("Php200.0O", "200.00"),
        ("Php12.345", None),
        ("Shop200.00", None),
    ],
)
def test_currency_variants(text, expected):
    assert parse_amount(text) == expected


def test_fuel_layout_tax_fields_date_and_following_quantity():
    result = extract(
        rows(
            "ROLLINGHILLS GASOLINE STATION",
            "Rollinghills San Nicolas",
            "Bamban, Tarlac",
            "Tin:131-154-330-000V",
            "PETRON Ramon L. Jimenez - Prop.",
            "Sales Receipt",
            "SI #: 514700",
            "Date: 2/4/2015 Time: 5:47:03 PM",
            "Cashier: CARLITO Register #: 2",
            "Description Amount",
            "Petron XTRA ADVANCE (D# 3) Php200.00",
            "6.3291 @ Php31.60",
            "Sub Total (12% Vatable) Php178.57",
            "Sub Total (Vat Exempt) Php0.00",
            "Plus 12% VAT Php21.43",
            "TOTAL AMOUNT TO BE PAID Php200.00",
            "Cash (PHP) Tendered Php200.00",
            "Change Cash Php0.00",
        ),
        "test",
    )
    for field, expected in {
        "merchant": "ROLLINGHILLS GASOLINE STATION",
        "receipt_number": "514700",
        "merchant_tin": "131-154-330-000",
        "receipt_date": "2015-02-04",
        "vatable_sales": "178.57",
        "vat_amount": "21.43",
        "vat_exempt": "0.00",
        "total": "200.00",
        "category": "Fuel",
    }.items():
        assert getattr(result, field).value == expected, field
    assert result.subtotal.value is None  # Tax components are not the generic subtotal.
    assert len(result.line_items) == 1
    item = result.line_items[0]
    assert (item.description, item.quantity, item.unit_price, item.amount) == (
        "Petron XTRA ADVANCE (D# 3)",
        "6.3291",
        "31.60",
        "200.00",
    )
    assert result.vatable_sales.source == "Sub Total (12% Vatable) Php178.57"
    assert result.receipt_date.confidence < 0.7
    assert any("older than 10 years" in warning for warning in result.warnings)
    assert len(result.checks) == 3 and all(check.passed for check in result.checks)


def test_quantity_is_not_a_second_item_or_attached_to_unrelated_item():
    result = extract(
        rows("SHOP", "Fuel PHP200.00", "6.3291 @ PHP31.60", "Oil PHP500.00", "TOTAL PHP700.00"),
        "test",
    )
    assert len(result.line_items) == 2
    assert result.line_items[0].quantity == "6.3291"
    assert result.line_items[1].quantity is None


def test_inconsistent_quantity_is_left_for_review():
    result = extract(rows("SHOP", "Fuel PHP200.00", "6.3291 @ PHP50.00", "TOTAL PHP200.00"), "test")
    assert len(result.line_items) == 1
    assert result.line_items[0].quantity is None


def test_quantity_before_item_and_currency_does_not_leak_into_description():
    result = extract(rows("SHOP", "2 @ PHP45.00", "Coffee PHP90.00", "TOTAL PHP90.00"), "test")
    assert result.line_items[0].description == "Coffee"
    assert result.line_items[0].quantity == "2"
    assert result.line_items[0].unit_price == "45.00"
