"""Advisors.

An advisor looks at a draft invoice and *proposes* a corrected copy. It is
never trusted: whatever it returns goes back through the same deterministic
gates before anything is accepted. Swapping a heuristic advisor for an
LLM-backed one is a one-class change and changes nothing about what is
allowed to become a finalized record.

This is the whole architectural point — the intelligence layer suggests,
the deterministic layer decides.
"""

from __future__ import annotations

from typing import Protocol

from .model import Invoice


class Advisor(Protocol):
    name: str

    def propose(self, draft: Invoice) -> Invoice:
        """Return a (possibly) corrected copy of `draft`. MUST NOT mutate
        the input. May return the draft unchanged if it sees nothing to fix."""
        ...


class NullAdvisor:
    """Proposes nothing. Used to measure the raw gate pass rate of incoming
    drafts before any assistance."""

    name = "null"

    def propose(self, draft: Invoice) -> Invoice:
        return draft


class HeuristicAdvisor:
    """Deterministic, offline, no model. Fixes the one class of error that is
    unambiguous: stated roll-ups that disagree with the line items. It rewrites
    stated_subtotal/tax/total to the recomputed truth and leaves everything
    else alone. It will never invent a line item or change a price — those are
    not arithmetic, they are judgement, and judgement does not get auto-applied.
    """

    name = "heuristic"

    def propose(self, draft: Invoice) -> Invoice:
        return draft.replace(
            stated_subtotal=draft.computed_subtotal,
            stated_tax=draft.computed_tax,
            stated_total=draft.computed_total,
        )


class LLMAdvisor:
    """Drop-in slot for a model-backed advisor (the production path).

    Intentionally unimplemented in the public proof-of-work: the contract is
    what matters here, not a key-gated demo. A real implementation prompts a
    model with the draft + vendor context, asks for a structured correction,
    and returns `draft.replace(**patch)`. It then goes through the *exact same*
    `gates.run_all`, so a hallucinated total can never reach a finalized
    record — it just fails the arithmetic gate like any other bad number.
    """

    name = "llm"

    def __init__(self, model: str = "<configure>") -> None:
        self.model = model

    def propose(self, draft: Invoice) -> Invoice:  # pragma: no cover
        raise NotImplementedError(
            "LLMAdvisor is the production seam. The proof-of-work ships the "
            "deterministic gates + HeuristicAdvisor so the safety property is "
            "verifiable offline; wiring a model changes only this method."
        )
