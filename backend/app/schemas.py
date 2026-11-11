import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

Status = Literal["queued", "processing", "needs_review", "verified", "failed"]
Category = Literal[
    "Food & Drinks",
    "Groceries",
    "Transport",
    "Fuel",
    "Utilities",
    "Office Supplies",
    "Health",
    "Other",
]
Box = tuple[int, int, int, int]
MONEY_FIELDS = ("subtotal", "vatable_sales", "vat_amount", "vat_exempt", "total")
TEXT_FIELDS = ("merchant", "merchant_tin", "receipt_number", "receipt_date", "category")


def valid_money(value: str) -> str:
    if not re.fullmatch(r"-?\d{1,10}(?:\.\d{1,2})?", value):
        raise ValueError("Use a decimal amount with at most two decimal places.")
    if abs(Decimal(value)) >= Decimal("10000000000"):
        raise ValueError("Amount is too large.")
    return f"{Decimal(value):.2f}"


Money = Annotated[str, AfterValidator(valid_money)]


class FieldValue(BaseModel):
    value: str | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    source: str | None = None
    box: Box | None = None


class OcrLine(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=1)
    box: Box


class Check(BaseModel):
    name: Literal["vat_math", "items_sum", "subtotal_vat_total"]
    passed: bool
    detail: str


class LineItemCandidate(BaseModel):
    description: str
    quantity: str | None = None
    unit_price: str | None = None
    amount: str
    confidence: float
    box: Box


class Extraction(BaseModel):
    merchant: FieldValue = Field(default_factory=FieldValue)
    merchant_tin: FieldValue = Field(default_factory=FieldValue)
    receipt_number: FieldValue = Field(default_factory=FieldValue)
    receipt_date: FieldValue = Field(default_factory=FieldValue)
    subtotal: FieldValue = Field(default_factory=FieldValue)
    vatable_sales: FieldValue = Field(default_factory=FieldValue)
    vat_amount: FieldValue = Field(default_factory=FieldValue)
    vat_exempt: FieldValue = Field(default_factory=FieldValue)
    total: FieldValue = Field(default_factory=FieldValue)
    category: FieldValue = Field(default_factory=FieldValue)
    line_items: list[LineItemCandidate] = Field(default_factory=list)
    checks: list[Check] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    engine_version: str


class QualityReport(BaseModel):
    blur_score: float
    is_blurry: bool
    brightness: float
    is_dark: bool
    skew_angle: float = 0
    document_found: bool = False
    warnings: list[str] = Field(default_factory=list)


class LineItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID | None = None
    position: int = Field(ge=0, le=500)
    description: str = Field(min_length=1, max_length=500)
    quantity: str | None = None
    unit_price: Money | None = None
    amount: Money

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Enter a line description.")
        return value.strip()

    @field_validator("quantity")
    @classmethod
    def quantity_decimal(cls, value):
        if value is not None and not re.fullmatch(r"\d{1,9}(?:\.\d{1,4})?", value):
            raise ValueError("Use a positive quantity with up to four decimal places.")
        return value


class ReceiptUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    merchant: str = Field(min_length=1, max_length=250)
    merchant_tin: str | None = Field(default=None, max_length=40)
    receipt_number: str | None = Field(default=None, max_length=100)
    receipt_date: date
    category: Category | None = None
    subtotal: Money | None = None
    vatable_sales: Money | None = None
    vat_amount: Money | None = None
    vat_exempt: Money | None = None
    total: Money
    line_items: list[LineItemInput] = Field(default_factory=list, max_length=500)

    @field_validator("merchant")
    @classmethod
    def merchant_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Enter the merchant name.")
        return value.strip()


class ReceiptSummary(BaseModel):
    id: UUID
    status: Status
    merchant: str | None
    receipt_number: str | None
    receipt_date: date | None
    total: str | None
    category: str | None
    thumbnail_url: str | None
    created_at: datetime
    error: str | None


class LineItemResponse(BaseModel):
    id: UUID
    position: int
    description: str
    quantity: str | None
    unit_price: str | None
    amount: str | None


class ReceiptImage(BaseModel):
    processed_url: str
    original_url: str
    width: int
    height: int


class JournalEntry(ReceiptSummary):
    merchant_tin: str | None
    subtotal: str | None
    vatable_sales: str | None
    vat_amount: str | None
    vat_exempt: str | None


class ReceiptDetail(JournalEntry):
    line_items: list[LineItemResponse]
    extraction: Extraction | None
    quality: QualityReport | None
    ocr_lines: list[OcrLine]
    image: ReceiptImage | None
    stages: dict[str, str]
    verified_at: datetime | None


class ReceiptList(BaseModel):
    items: list[ReceiptSummary]
    next_cursor: str | None


class JournalList(BaseModel):
    items: list[JournalEntry]
    next_cursor: str | None


class UploadResult(BaseModel):
    id: UUID
    status: Status


class CategoryTotal(BaseModel):
    category: str
    total: str
    count: int


class DayTotal(BaseModel):
    date: date
    total: str


class MonthlySummary(BaseModel):
    month: str
    total: str
    vat_total: str
    count: int
    by_category: list[CategoryTotal]
    by_day: list[DayTotal]


class WorkspaceToken(BaseModel):
    token: str
