# invoice-guard

> 🎯 **Proof-of-Concept for [C4GT DMP 2026 — Issue #37](https://github.com/seetadev/GovtInvoice/issues/37)**
> *Agentic Invoice Co-Pilot for Government Billing · NSUT × SEETA × AIC*
>
> This repository is the **Validation Gate (Layer 2)** of the DMP proposal.
> The 12-week plan ports this gate into [Govt-Billing-React](https://github.com/seetadev/GovtInvoice)'s save path and wraps [py-ipfs-lite](https://github.com/seetadev/py-ipfs-lite) for canonical CID emission.
>
> Proposal discussion: [GovtInvoice Discussion #89](https://github.com/seetadev/GovtInvoice/discussions/89)
> By **Vanshikha Sri** · B.Tech, IIIT Jabalpur · [@zsklav](https://github.com/zsklav)

---

A deterministic validation and anomaly gate for invoice data, with a pluggable advisor seam.

The idea is small and deliberately boring: **an intelligence layer may suggest corrections to an invoice, but it never decides whether one becomes a finalized financial record.** That decision belongs to deterministic, offline, reproducible gates that produce the same verdict for the same invoice on any machine, forever. Swapping a rule-based advisor for a model-backed one cannot widen what is allowed through.

## Why

Invoice automation usually fails in one of two ways: a model confidently emits a number that doesn't reconcile, or a brittle pile of UI checks lets a blank or negative invoice through. `invoice-guard` separates the two concerns cleanly — suggestion from adjudication — so the part that touches money stays auditable even as the smart part changes.

## Design

```
draft ─▶ gate(draft)        what came in
      ─▶ advisor.propose    a suggested fix — untrusted
      ─▶ overreach check    advisor may only rewrite the roll-ups
      ─▶ gate(proposed)     the suggestion earns its place or it doesn't
      ─▶ Decision           ACCEPT · REVIEW · REJECT
```

Three gates, all pure functions:

| Gate | What it guarantees |
|---|---|
| **completeness** | identity, line items, ISO date present — no half-invoices |
| **arithmetic** | line items recompute *exactly* (`decimal.Decimal`, no float, no tolerance) to the stated subtotal / tax / total; no negative or non-positive amounts |
| **anomaly** | duplicate invoice number, future date, or a total far from this vendor's history → `REVIEW` (a human looks before money moves), never a silent pass |

An advisor implements one method, `propose(draft) -> Invoice`. The bundled `HeuristicAdvisor` repairs the one unambiguous error class (stated roll-ups that disagree with the line items) and nothing else. `LLMAdvisor` is the documented production seam — wiring a model changes only that one method; the gates are unchanged, so a hallucinated total fails the arithmetic gate like any other bad number.

## Quickstart

No dependencies. Python 3.10+.

```bash
git clone https://github.com/zsklav/invoice-guard
cd invoice-guard
PYTHONPATH=src python3 -m invoice_guard          # bundled samples
PYTHONPATH=src python3 -m invoice_guard my.jsonl # your own drafts
python3 -m unittest discover -s tests            # the safety property
```

Real output on the bundled set:

```
invoice    no advisor             + heuristic            note
-------------------------------------------------------------
INV-1001   ACCEPT                 ACCEPT                 clean — should ACCEPT untouched
INV-1002   REJECT                 ACCEPT                 roll-up typo — heuristic fixes, then ACCEPT
INV-1003   REJECT                 REJECT                 negative line — advisor cannot rescue
∅          REJECT                 REJECT                 missing invoice_number
INV-1001   REVIEW                 REVIEW                 duplicate number — possible double-bill
INV-1009   REVIEW                 REVIEW                 ~200x vendor history — outlier

roll-up typos repaired by the deterministic advisor : 1
real defects laundered into ACCEPT (must be 0)       : 0

PASS — the advisor only ever rescued arithmetic-typo rejects;
every structural/sign defect stayed rejected.
```

The last two lines are the point. The advisor is *useful* (it repaired a typo that would otherwise have been rejected) without being *trusted* (it could not turn a negative, incomplete, or duplicate invoice into an accepted record). The test suite pins that property, including an explicit rogue-advisor case.

## C4GT DMP 2026 — Integration plan

This POC is the foundation for a 12-week DMP project that integrates the Validation Gate into `seetadev/GovtInvoice`:

| Weeks | Phase | Deliverable |
|---|---|---|
| **1–2** | Integrity first | Port this gate into `Govt-Billing-React/src/services/InvoiceValidator.ts` (Issue #48's stated file). Make `Local._saveFile` private; expose `Local.validatedSave(file)` as the only public entry. Update all 4 save-path call sites. |
| **3–4** | Agentic seam | FastAPI Advisor microservice. `LLMAdvisor` interface gets a real model behind it. |
| **5–6** | **Mid-point milestone** | PWA Co-Pilot live — no invalid invoice can be saved or pinned. Mentor-verifiable from a fresh clone. |
| **7–8** | CID finalization | Wrap [`py-ipfs-lite`](https://github.com/seetadev/py-ipfs-lite)'s `block_service.BlockService` for dual-CID emission (canonical `dag-cbor` + UnixFS artifact). |
| **9–10** | Payment adapters | `PaymentAdapter` Protocol with `X402Adapter`, `MPPAdapter`, `ERC8004Adapter`, `MockAdapter`. Testnet demo. |
| **11–12** | Anomaly + HITL + handoff | REVIEW queue UI, reproducibility docs, mentor handoff session. |

**Verified safety property** — pinned in the test suite, validated on every CI run:
> *No real defect ever reaches a finalized invoice — `defects_in_ACCEPT == 0`.*

### Useful links

- 📄 [Issue #37 — DMP Brief](https://github.com/seetadev/GovtInvoice/issues/37)
- 📂 [Issue #48 — closes by construction](https://github.com/seetadev/GovtInvoice/issues/48)
- 💬 [Discussion #89 — proposal discussion](https://github.com/seetadev/GovtInvoice/discussions/89)
- 🔧 [py-ipfs-lite — first-class IPFS dependency](https://github.com/seetadev/py-ipfs-lite)

**Mentors:** [@seetadev](https://github.com/seetadev) (Manu Sheel Gupta), [@aspiringsecurity](https://github.com/aspiringsecurity), [@prithagupta](https://github.com/prithagupta), and Dr. MPS Bhatia (faculty adviser).

## Status

Standard library only, by design — the gate logic has to be readable and auditable end to end. The model-backed advisor is a defined interface, not a bundled demo: the safety guarantee is what is verifiable here, offline.

MIT licensed.
