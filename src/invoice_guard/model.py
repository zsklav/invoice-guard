"""Invoice data model.

Money is `decimal.Decimal` everywhere. Floats are never used for amounts:
a financial record that fails to round-trip exactly is a defect, not a
tolerance to be tuned away.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

CENTS = Decimal("0.01")


def money(value: Any) -> Decimal:
    """Parse a value into a 2dp Decimal. Raises on anything non-numeric.

    Strings are parsed exactly (`Decimal("19.99")`), so no float drift is
    introduced at the boundary.
    """
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"not a valid money value: {value!r}") from exc
    return d.quantize(CENTS)


@dataclass(frozen=True)
class LineItem:
    description: str
    quantity: Decimal
    unit_price: Decimal

    @property
    def amount(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(CENTS)

    @staticmethod
    def from_dict(d: dict) -> "LineItem":
        return LineItem(
            description=str(d.get("description", "")).strip(),
            quantity=money(d.get("quantity", 0)),
            unit_price=money(d.get("unit_price", 0)),
        )


@dataclass(frozen=True)
class Invoice:
    """A draft invoice. `stated_*` are the numbers as submitted; the gates
    recompute the truth and compare. The draft is never mutated in place."""

    invoice_number: str
    vendor: str
    issue_date: str  # ISO yyyy-mm-dd
    line_items: tuple[LineItem, ...]
    tax_rate: Decimal           # e.g. Decimal("0.18")
    stated_subtotal: Decimal
    stated_tax: Decimal
    stated_total: Decimal
    currency: str = "INR"
    meta: dict = field(default_factory=dict)

    # ---- derived truth (never read from the submitted numbers) ----
    @property
    def computed_subtotal(self) -> Decimal:
        return sum((li.amount for li in self.line_items), Decimal("0")).quantize(CENTS)

    @property
    def computed_tax(self) -> Decimal:
        return (self.computed_subtotal * self.tax_rate).quantize(CENTS)

    @property
    def computed_total(self) -> Decimal:
        return (self.computed_subtotal + self.computed_tax).quantize(CENTS)

    @staticmethod
    def from_dict(d: dict) -> "Invoice":
        return Invoice(
            invoice_number=str(d.get("invoice_number", "")).strip(),
            vendor=str(d.get("vendor", "")).strip(),
            issue_date=str(d.get("issue_date", "")).strip(),
            line_items=tuple(
                LineItem.from_dict(li) for li in d.get("line_items", [])
            ),
            tax_rate=money(d.get("tax_rate", 0)) if "." in str(d.get("tax_rate", "0"))
            else Decimal(str(d.get("tax_rate", "0"))),
            stated_subtotal=money(d.get("stated_subtotal", 0)),
            stated_tax=money(d.get("stated_tax", 0)),
            stated_total=money(d.get("stated_total", 0)),
            currency=str(d.get("currency", "INR")).strip() or "INR",
            meta=dict(d.get("meta", {})),
        )

    def replace(self, **changes: Any) -> "Invoice":
        """Return a new Invoice with fields changed. The original is frozen,
        so a corrected copy is always a distinct object the caller can diff."""
        from dataclasses import replace as _replace

        return _replace(self, **changes)
