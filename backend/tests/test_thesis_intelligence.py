from datetime import datetime, timezone
from decimal import Decimal

from app.thesis_intelligence import ThesisIntelligenceService


def row(state="DETECTED"):
    return {
        "current_state": state,
        "direction": "BUY",
        "original_entry_lower": Decimal("100"),
        "original_entry_upper": Decimal("102"),
        "original_stop": Decimal("95"),
        "original_target": Decimal("110"),
    }


def candle(low, high):
    return {
        "timestamp": datetime(2026, 10, 27, tzinfo=timezone.utc),
        "low": Decimal(str(low)),
        "high": Decimal(str(high)),
    }


def test_entry_and_monitoring_are_distinct_from_terminal_target():
    assert ThesisIntelligenceService._state_for_candle(row(), candle(101, 101.5), datetime.now(timezone.utc)) == "ENTRY_AVAILABLE"
    assert ThesisIntelligenceService._state_for_candle(row("ENTRY_AVAILABLE"), candle(101, 111), datetime.now(timezone.utc)) == "INITIAL_TARGET_REACHED"


def test_same_candle_barrier_order_is_ambiguous():
    assert ThesisIntelligenceService._state_for_candle(row("MONITORING"), candle(94, 111), datetime.now(timezone.utc)) == "OUTCOME_AMBIGUOUS"


def test_entry_missed_and_invalidation_are_not_fills():
    assert ThesisIntelligenceService._state_for_candle(row(), candle(103, 104), datetime.now(timezone.utc)) == "ENTRY_MISSED"
    assert ThesisIntelligenceService._state_for_candle(row("MONITORING"), candle(90, 96), datetime.now(timezone.utc)) == "INVALIDATED"
