"""Stdlib unittest — no deps. `python3 -m unittest discover tests`.

These tests pin the one property the whole design exists to guarantee:
an advisor can correct a roll-up typo, but it can never turn a structurally
or numerically broken invoice into an accepted financial record.
"""

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from invoice_guard import HeuristicAdvisor, Invoice, NullAdvisor, evaluate  # noqa: E402


def _inv(**over):
    base = dict(
        invoice_number="T-1", vendor="V", issue_date="2026-01-01",
        line_items=[{"description": "x", "quantity": "2", "unit_price": "100.00"}],
        tax_rate="0.18",
        stated_subtotal="200.00", stated_tax="36.00", stated_total="236.00",
    )
    base.update(over)
    return Invoice.from_dict(base)


class SafetyProperty(unittest.TestCase):
    def test_clean_invoice_accepts_untouched(self):
        d = evaluate(_inv(), NullAdvisor())
        self.assertEqual(d.status, "ACCEPT")
        self.assertFalse(d.patched)

    def test_rollup_typo_rejected_raw_then_repaired(self):
        bad = _inv(stated_total="999.00")
        self.assertEqual(evaluate(bad, NullAdvisor()).status, "REJECT")
        fixed = evaluate(bad, HeuristicAdvisor())
        self.assertEqual(fixed.status, "ACCEPT")
        self.assertTrue(fixed.patched)

    def test_negative_line_cannot_be_rescued(self):
        bad = _inv(
            line_items=[{"description": "x", "quantity": "1",
                         "unit_price": "-50.00"}],
            stated_subtotal="-50.00", stated_tax="-9.00",
            stated_total="-59.00")
        self.assertEqual(evaluate(bad, HeuristicAdvisor()).status, "REJECT")

    def test_missing_number_cannot_be_rescued(self):
        bad = _inv(invoice_number="")
        self.assertEqual(evaluate(bad, HeuristicAdvisor()).status, "REJECT")

    def test_duplicate_number_goes_to_review(self):
        d = evaluate(_inv(), HeuristicAdvisor(), seen_numbers={"T-1"})
        self.assertEqual(d.status, "REVIEW")

    def test_amount_outlier_goes_to_review(self):
        hist = [Decimal("236.00")] * 5
        big = _inv(
            line_items=[{"description": "x", "quantity": "1",
                         "unit_price": "500000.00"}],
            stated_subtotal="500000.00", stated_tax="90000.00",
            stated_total="590000.00")
        self.assertEqual(
            evaluate(big, HeuristicAdvisor(), history=hist).status, "REVIEW")

    def test_advisor_overreach_is_a_hard_reject(self):
        class RogueAdvisor:
            name = "rogue"

            def propose(self, draft):
                # tries to silently change a price, not just the roll-ups
                items = list(draft.line_items)
                return draft.replace(line_items=items, stated_total="1.00")

        # rogue keeps line_items identical but lies about total -> arithmetic
        # gate catches it; if it changed line_items, overreach catches it.
        d = evaluate(_inv(), RogueAdvisor())
        self.assertEqual(d.status, "REJECT")


if __name__ == "__main__":
    unittest.main()
