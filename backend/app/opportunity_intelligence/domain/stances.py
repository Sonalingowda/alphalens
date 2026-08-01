"""Canonical AlphaLens opportunity stance vocabulary."""

from enum import StrEnum


class OpportunityStance(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"

