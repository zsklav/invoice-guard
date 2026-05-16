"""Deterministic gates.

Every gate is a pure function of the invoice (plus, for the anomaly gate,
a read-only history). No gate calls a model, touches the network, or mutates
input. This is the part that must be boring and auditable: the same invoice
always produces the same gate verdicts, on any machine, forever.
"""

from __future__ import annotations

import datetime as _dt
import statistics
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .model import Invoice

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


@dataclass(frozen=True)
class GateResult:
    gate: str
    status: str          # PASS | WARN | FAIL
    code: str            # stable machine code, safe to log/alert on
    message: str

    @property
    def blocking(self) -> bool:
        return self.status == FAIL


# --------------------------------------------------------------------------- #
# 1. Completeness — an invoice missing identity or lines is not an invoice.    #
#    (This is the class of bug the upstream repo's issue #48 / PR #50 fixed    #
#    by hand; here it is one declarative gate instead of scattered UI checks.) #
# --------------------------------------------------------------------------- #
def completeness_gate(inv: Invoice) -> GateResult:
    g = "completeness"
    if not inv.invoice_number:
        return GateResult(g, FAIL, "MISSING_NUMBER", "invoice_number is empty")
    if not inv.vendor:
        return GateResult(g, FAIL, "MISSING_VENDOR", "vendor is empty")
    if not inv.line_items:
        return GateResult(g, FAIL, "NO_LINE_ITEMS", "invoice has zero line items")
    for i, li in enumerate(inv.line_items):
        if not li.description:
            return GateResult(g, FAIL, "BLANK_LINE_DESC",
                              f"line item {i} has no description")
    try:
        _dt.date.fromisoformat(inv.issue_date)
    except ValueError:
        return GateResult(g, FAIL, "BAD_DATE",
                          f"issue_date not ISO yyyy-mm-dd: {inv.issue_date!r}")
    return GateResult(g, PASS, "OK", "all required fields present")


# --------------------------------------------------------------------------- #
# 2. Arithmetic — recompute the truth from line items and compare to the       #
#    submitted numbers. Exact Decimal equality, no tolerance: a financial      #
#    record either reconciles or it does not.                                  #
# --------------------------------------------------------------------------- #
def arithmetic_gate(inv: Invoice) -> GateResult:
    g = "arithmetic"
    for i, li in enumerate(inv.line_items):
        if li.quantity < 0:
            return GateResult(g, FAIL, "NEG_QTY",
                              f"line {i} quantity is negative: {li.quantity}")
        if li.unit_price < 0:
            return GateResult(g, FAIL, "NEG_PRICE",
                              f"line {i} unit_price is negative: {li.unit_price}")
    if inv.computed_total <= 0:
        return GateResult(g, FAIL, "NON_POSITIVE_TOTAL",
                          f"computed total is {inv.computed_total} (must be > 0)")
    if inv.stated_subtotal != inv.computed_subtotal:
        return GateResult(g, FAIL, "SUBTOTAL_MISMATCH",
                          f"stated subtotal {inv.stated_subtotal} != "
                          f"computed {inv.computed_subtotal}")
    if inv.stated_tax != inv.computed_tax:
        return GateResult(g, FAIL, "TAX_MISMATCH",
                          f"stated tax {inv.stated_tax} != "
                          f"computed {inv.computed_tax}")
    if inv.stated_total != inv.computed_total:
        return GateResult(g, FAIL, "TOTAL_MISMATCH",
                          f"stated total {inv.stated_total} != "
                          f"computed {inv.computed_total}")
    return GateResult(g, PASS, "OK",
                      f"reconciles exactly at {inv.currency} {inv.computed_total}")


# --------------------------------------------------------------------------- #
# 3. Anomaly — structural + history checks. These WARN, they do not FAIL:      #
#    an unusual invoice is not a wrong invoice, but it is the one a human      #
#    should look at before money moves.                                        #
# --------------------------------------------------------------------------- #
def anomaly_gate(inv: Invoice, history: Iterable[Decimal] = (),
                  seen_numbers: Iterable[str] = (),
                  k: Decimal = Decimal("3")) -> GateResult:
    g = "anomaly"

    if inv.invoice_number in set(seen_numbers):
        return GateResult(g, WARN, "DUPLICATE_NUMBER",
                          f"invoice_number {inv.invoice_number!r} already seen "
                          f"— possible double-billing")

    try:
        d = _dt.date.fromisoformat(inv.issue_date)
        if d > _dt.date.today():
            return GateResult(g, WARN, "FUTURE_DATE",
                              f"issue_date {inv.issue_date} is in the future")
    except ValueError:
        pass  # completeness_gate already owns the hard failure

    hist = [Decimal(str(h)) for h in history]
    if len(hist) >= 3:
        mu = statistics.fmean(float(h) for h in hist)
        sd = statistics.pstdev(float(h) for h in hist)
        val = float(inv.computed_total)
        if sd > 0:
            z = (val - mu) / sd
            if abs(z) >= float(k):
                return GateResult(g, WARN, "AMOUNT_OUTLIER",
                                  f"total {inv.computed_total} is {z:+.1f}σ from "
                                  f"this vendor's mean ({mu:.2f}) — review")
        elif mu > 0 and abs(val - mu) / mu >= 0.5:
            # Zero-variance history (a recurring fixed invoice). σ is
            # undefined, so fall back to a relative-deviation check: a value
            # ≥50% off a perfectly stable baseline is exactly the case a
            # human should see before money moves.
            pct = (val - mu) / mu * 100
            return GateResult(g, WARN, "AMOUNT_OUTLIER",
                              f"total {inv.computed_total} is {pct:+.0f}% off "
                              f"this vendor's stable baseline ({mu:.2f}) — review")

    return GateResult(g, PASS, "OK", "no structural or historical anomaly")


def run_all(inv: Invoice, history: Iterable[Decimal] = (),
            seen_numbers: Iterable[str] = ()) -> list[GateResult]:
    return [
        completeness_gate(inv),
        arithmetic_gate(inv),
        anomaly_gate(inv, history=history, seen_numbers=seen_numbers),
    ]
