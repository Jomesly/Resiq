"""Loyalty points, rewards balances and footers must never become money on the receipt."""

import pytest

from app.extraction import extract, parse_amount
from app.schemas import OcrLine


def lines(*texts):
    return [
        OcrLine(text=t, confidence=0.95, box=(10, i * 30, 500, i * 30 + 20))
        for i, t in enumerate(texts)
    ]


# Real PaddleOCR rows from a Robinsons Supermarket receipt (customer name and card number replaced).
ROBINSONS = (
    "Robinsons",
    "Supermarket",
    "ROBINSON'S SUPERMARKET CORPORATION",
    "VAT REG TIN 000-405-340-020",
    "ROBINSONS GALLERIA",
    "EDSA CORNER ORTIGAS AVENUE",
    "QUEZON CITY",
    "Name:",
    "TIN:",
    "ID No:",
    "Address:",
    "Business Style:",
    "Signature:",
    "CHARMEE AN LONG 10S 62.00 V",
    "04800488961475",
    "TOTAL P62.00",
    "CASH P1,000.00",
    "Change P938.00",
    "******************************************",
    "Vatable 55.36",
    "VAT Exempt Sales 0.00",
    "Zero Rated Sales 0.00",
    "VAT 6.64",
    "Total 62.00",
    "******************************************",
    "************ Go Rewards ***********",
    "Card Number :8110000000000000 2",
    "Customer Name: JUAN DELA CRUZ",
    "Card Expiry : 12/30/2056",
    "Available Balance : 402.191",
    "Earned Points 8 0.15",
    "Current Balance 402.34",
    "******************************************",
    "Total Items: 1",
    "Cashier: 616 Bayani, Cristal",
    "Str No: 0101 Date:02/01/2024 Time:19:57:24",
    "Terminal No: 0012 Trans ID: 3813",
    "This serves as your Sales Invoice",
    "SI No: 0000098076",
    "Robinson's Supermarket Corporation",
    "110 E.Rodriguez Jr. Ave., Bagumbayan QC",
    "ACCDTN NO.: 116-000405340-000340-57230",
    "Issued 08/29/12, Effective 08/01/20",
    "TIN:000-405-340-000",
    "SN: TXMB0106",
    "PN: FP032023-116-0373937-00020",
    "MIN: 23030811524766612",
    "SPM :S SP032023-116-0116223-00020",
)


def test_robinsons_go_rewards_block_is_not_money():
    result = extract(lines(*ROBINSONS), "paddle")
    assert result.total.value == "62.00"
    assert [(i.description, i.amount) for i in result.line_items] == [
        ("CHARMEE AN LONG 10S", "62.00")
    ]
    assert all(c.passed for c in result.checks), result.checks
    assert result.vatable_sales.value == "55.36"
    assert result.vat_amount.value == "6.64"
    assert result.receipt_date.value == "2024-02-01"
    assert result.receipt_number.value == "0000098076"
    assert result.warnings == []


def test_store_vat_tin_wins_over_pos_supplier_footer_tin():
    result = extract(lines(*ROBINSONS), "paddle")
    assert result.merchant_tin.value == "000-405-340-020"


def test_colon_misread_as_digit_does_not_join_numbers():
    assert parse_amount("Earned Points 8 0.15") == "0.15"
    assert parse_amount("₱1 250.00") == "1250.00"
    assert parse_amount("P 12 345 678.90") == "12345678.90"


BASE = (
    "SM SUPERMARKET",
    "VAT REG TIN 000-123-456-000",
    "11/09/2026 12:41 PM",
    "BREAD 90.00",
    "MILK 45.00",
    "VATABLE SALES 120.54",
    "VAT 12% 14.46",
    "TOTAL 135.00",
    "CASH 200.00",
    "CHANGE 65.00",
)


@pytest.mark.parametrize(
    "footer",
    [
        ("POINTS EARNED 1.35",),
        ("TOTAL POINTS 12.50",),
        ("SM ADVANTAGE POINTS BAL 1,234.50",),
        ("REWARDS EARNED 2.70", "PTS 1.35"),
        ("Suki Card Balance 88.00",),
        ("PROMO VOUCHER FOR NEXT VISIT 50.00",),
    ],
)
def test_points_and_footer_lines_never_become_total_or_items(footer):
    result = extract(lines(*BASE, *footer), "paddle")
    assert result.total.value == "135.00"
    assert [i.description for i in result.line_items] == ["BREAD", "MILK"]
    assert all(c.passed for c in result.checks), result.checks


def test_points_used_as_payment_do_not_change_total_or_items():
    result = extract(
        lines(*BASE[:8], "POINTS REDEEMED 35.00", "CASH 100.00", "CHANGE 0.00"), "paddle"
    )
    assert result.total.value == "135.00"
    assert [i.description for i in result.line_items] == ["BREAD", "MILK"]


@pytest.mark.parametrize("item", ["BALLPOINT PEN 25.00", "POINT PEN 25.00"])
def test_products_named_point_stay_items(item):
    result = extract(lines("NATIONAL BOOK STORE", item, "TOTAL 25.00"), "paddle")
    assert [(i.description, i.amount) for i in result.line_items] == [(item[:-6], "25.00")]


def test_reconciling_total_beats_a_later_stray_total():
    result = extract(lines(*BASE, "TOTAL 1.00"), "paddle")
    assert result.total.value == "135.00"


def test_zero_rated_sales_count_in_the_tax_breakdown():
    result = extract(
        lines(
            "SHOP",
            "ITEM 145.00",
            "VATABLE SALES 120.54",
            "VAT 14.46",
            "ZERO RATED SALES 10.00",
            "TOTAL 145.00",
        ),
        "paddle",
    )
    assert all(c.passed for c in result.checks), result.checks


def test_extraction_version_is_rules_3():
    assert extract(lines("SHOP", "TOTAL 1.00"), "paddle").engine_version == "paddle/rules-3"
