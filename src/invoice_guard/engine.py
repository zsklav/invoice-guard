"""The pipeline.

    draft ──▶ gate(draft)          (what came in)
          ──▶ advisor.propose      (a suggested fix — untrusted)
          ──▶ overreach check      (advisor may only touch the roll-ups)
          ──▶ gate(proposed)       (the suggestion earns its place or doesn't)
          ──▶ Decision

A Decision is one of:
  ACCEPT  every gate PASSes — safe to finalize
  REVIEW  no FAILs, but an anomaly WARNed — a human looks before money moves
  REJECT  at least one gate FAILed — cannot become a finalized record

The advisor never decides anything. It only ever produces a candidate that
then has to survive the same deterministic gates as the raw draft.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

from .advisor import Advisor, NullAdvisor
from .gates import FAIL, WARN, GateResult, run_all
from .model import Invoice

# Fields an advisor is allowed to rewrite. Touching anything else (a price, a
# line item, the vendor) is overreach and is itself a hard failure — that is
# how "the model suggests, it does not edit the ledger" is enforced in code.
_ADVISOR_WRITABLE = {"stated_subtotal", "stated_tax", "stated_total"}


@dataclass(frozen=True)
class Decision:
    invoice_number: str
    status: str                      # ACCEPT | REVIEW | REJECT
    advisor: str
    patched: bool                    # did the advisor change anything
    raw_results: list[GateResult]
    final_results: list[GateResult]
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ACCEPT"


def _overreach(draft: Invoice, proposed: Invoice) -> list[str]:
    """Return human-readable descriptions of any change the advisor made
    outside the writable roll-up fields."""
    bad = []
    if proposed.line_items != draft.line_items:
        bad.append("advisor altered line_items (not permitted)")
    for f in ("invoice_number", "vendor", "issue_date", "tax_rate", "currency"):
        if getattr(proposed, f) != getattr(draft, f):
            bad.append(f"advisor altered {f} (not permitted)")
    return bad


def evaluate(draft: Invoice, advisor: Advisor | None = None,
             history: Iterable[Decimal] = (),
             seen_numbers: Iterable[str] = ()) -> Decision:
    advisor = advisor or NullAdvisor()
    notes: list[str] = []

    raw = run_all(draft, history=history, seen_numbers=seen_numbers)

    proposed = advisor.propose(draft)
    if proposed is draft or proposed == draft:
        patched = False
        final = raw
    else:
        patched = True
        over = _overreach(draft, proposed)
        if over:
            notes.extend(over)
            return Decision(draft.invoice_number, "REJECT", advisor.name,
                            True, raw,
                            [GateResult("advisor", FAIL, "ADVISOR_OVERREACH",
                                        "; ".join(over))],
                            notes)
        notes.append(
            f"advisor '{advisor.name}' rewrote roll-ups: "
            f"total {draft.stated_total} → {proposed.stated_total}")
        final = run_all(proposed, history=history, seen_numbers=seen_numbers)

    if any(r.status == FAIL for r in final):
        status = "REJECT"
    elif any(r.status == WARN for r in final):
        status = "REVIEW"
    else:
        status = "ACCEPT"

    return Decision(draft.invoice_number, status, advisor.name,
                    patched, raw, final, notes)
