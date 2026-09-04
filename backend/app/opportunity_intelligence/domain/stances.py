"""Canonical AlphaLens opportunity stance vocabulary."""

try:
    from enum import StrEnum
except Exception:  # pragma: no cover - compatibility shim for Python < 3.11
    from enum import Enum

    class StrEnum(str, Enum):
        """Compatibility fallback for enum.StrEnum on older Pythons."""
        def __str__(self) -> str:  # keep behavior compatible with StrEnum
            return str(self.value)


class OpportunityStance(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"

