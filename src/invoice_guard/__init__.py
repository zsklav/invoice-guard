"""invoice-guard — a deterministic validation and anomaly gate for invoice
data, with a pluggable advisor seam.

The intelligence layer (rules today, a model tomorrow) may only *propose*
corrections. Whether anything becomes a finalized financial record is decided
entirely by deterministic, offline, reproducible gates. Swapping the advisor
cannot widen what is allowed through.
"""

from .advisor import HeuristicAdvisor, LLMAdvisor, NullAdvisor
from .engine import Decision, evaluate
from .gates import GateResult, run_all
from .model import Invoice, LineItem, money

__all__ = [
    "Invoice", "LineItem", "money",
    "GateResult", "run_all",
    "Decision", "evaluate",
    "NullAdvisor", "HeuristicAdvisor", "LLMAdvisor",
]

__version__ = "0.1.0"
