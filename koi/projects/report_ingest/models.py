"""Contracts for parsing and applying experiment report claims."""

from dataclasses import dataclass, field
from typing import Optional


class ReportIngestError(ValueError):
    """The report cannot be integrated; the message explains what to fix."""


@dataclass
class ReportClaim:
    """Machine-readable knowledge claim extracted from a ``.run.md`` report."""

    cause_id: Optional[str] = None
    verdict: Optional[str] = None
    method_id: Optional[str] = None
    card_id: Optional[str] = None
    insights: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
