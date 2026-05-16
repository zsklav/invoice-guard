"""Offline demo runner.

    PYTHONPATH=src python3 -m invoice_guard               # bundled samples
    PYTHONPATH=src python3 -m invoice_guard path/to.jsonl # your own

Runs every draft twice — once with no advisor (raw inbound quality) and once
with the deterministic HeuristicAdvisor — and prints the verdicts side by
side. The headline it ends on is the safety property, not an accuracy score:
no REJECT-class invoice is ever turned into an ACCEPT by the advisor.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

from .advisor import HeuristicAdvisor, NullAdvisor
from .engine import evaluate
from .model import Invoice

_DEFAULT = Path(__file__).resolve().parent.parent.parent / "samples" / "sample_invoices.jsonl"


def _load(path: Path) -> list[Invoice]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(Invoice.from_dict(json.loads(line)))
    return rows


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else _DEFAULT
    if not path.exists():
        print(f"no such file: {path}", file=sys.stderr)
        return 2

    drafts = _load(path)

    # vendor history for the anomaly gate (totals seen before this run)
    history: dict[str, list[Decimal]] = {}
    seen: set[str] = set()

    print(f"invoice-guard · {len(drafts)} draft(s) · source {path.name}\n")
    header = f"{'invoice':<10} {'no advisor':<22} {'+ heuristic':<22} note"
    print(header)
    print("-" * len(header))

    rescued = unsafe = 0
    for d in drafts:
        h = history.get(d.vendor, [])
        raw = evaluate(d, NullAdvisor(), history=h, seen_numbers=seen)
        fixed = evaluate(d, HeuristicAdvisor(), history=h, seen_numbers=seen)

        if raw.status == "REJECT" and fixed.status in ("ACCEPT", "REVIEW"):
            # only legitimate if the rejection was a pure roll-up mismatch
            codes = {r.code for r in raw.final_results if r.status == "FAIL"}
            if codes <= {"SUBTOTAL_MISMATCH", "TAX_MISMATCH", "TOTAL_MISMATCH"}:
                rescued += 1
            else:
                unsafe += 1  # advisor laundered a real defect — must never happen

        note = d.meta.get("case", "")
        print(f"{(d.invoice_number or '∅'):<10} "
              f"{raw.status:<22} {fixed.status:<22} {note}")

        seen.add(d.invoice_number)
        if fixed.status in ("ACCEPT", "REVIEW"):
            history.setdefault(d.vendor, []).append(d.computed_total)

    print()
    print(f"roll-up typos repaired by the deterministic advisor : {rescued}")
    print(f"real defects laundered into ACCEPT (must be 0)       : {unsafe}")
    print()
    print("PASS — the advisor only ever rescued arithmetic-typo rejects; "
          "every structural/sign defect stayed rejected."
          if unsafe == 0 else
          "FAIL — a real defect was laundered. The safety property is broken.")
    return 0 if unsafe == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
