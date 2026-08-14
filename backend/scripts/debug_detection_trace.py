"""Simple trace to identify why opportunities don't persist to dashboard."""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256

logging.basicConfig(
    level=logging.INFO,
    format='[%(name)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("trace")

from app.live_market_data.service import LiveMarketIngestionService
from app.live_market_data.binance import BinanceKlineParser, BinanceWebSocketClient
from app.live_market_data.models import CompletedCandle
from app.live_market_data.snapshots import build_market_snapshot
from app.market_data.models import CandleTimeframe

from app.opportunity_intelligence.persistence.memory import (
    MarketSnapshotMemoryRepository,
    FeatureSnapshotMemoryRepository,
    MarketContextMemoryRepository,
    DetectionMemoryRepository,
    EvidenceMemoryRepository,
    OpportunityMemoryRepository,
    QualificationMemoryRepository,
    ScoringMemoryRepository,
    RankingMemoryRepository,
    DashboardProjectionMemoryRepository,
    OpportunityDetailMemoryRepository,
)

from app.runtime_features.engine import RuntimeFeatureEngine
from app.runtime_context.service import RuntimeMarketContextService
from app.runtime_detection.service import RuntimeOpportunityDetectionService
from app.opportunity_intelligence.domain import MarketScope
from app.opportunity_intelligence.repositories import ScopedRepositoryQuery

import httpx


async def main():
    logger.info("=" * 80)
    logger.info("FOCUSED TRACE: Detection → Dashboard")
    logger.info("=" * 80)

    # Create repos
    markets = MarketSnapshotMemoryRepository()
    features = FeatureSnapshotMemoryRepository()
    contexts = MarketContextMemoryRepository()
    detections = DetectionMemoryRepository()
    evidence_repo = EvidenceMemoryRepository()
    opportunities = OpportunityMemoryRepository()
    dashboard_repo = DashboardProjectionMemoryRepository()

    # Services
    feature_engine = RuntimeFeatureEngine(market_snapshots=markets, feature_snapshots=features, code_version="trace.1.0.0")
    context_service = RuntimeMarketContextService(market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, code_version="trace.1.0.0")
    detection_service = RuntimeOpportunityDetectionService(market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, detections=detections, code_version="trace.1.0.0")

    # Prefill 600 5m candles
    logger.info("PREFILL: Fetching 600 5m candles from Binance...")
    now = datetime.now(timezone.utc)
    floor_minutes = (now.minute // 5) * 5
    end = now.replace(minute=floor_minutes, second=0, microsecond=0)
    end_ms = int(end.timestamp() * 1000)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": "BTCUSDT", "interval": "5m", "limit": 600, "endTime": end_ms},
            timeout=30,
        )
        resp.raise_for_status()
        klines = resp.json()

    logger.info(f"PREFILL: Fetched {len(klines)} klines")

    for k in klines:
        open_ms = int(k[0])
        open_time = datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc)
        close_ms = int(k[6])
        close_time = datetime.fromtimestamp(close_ms / 1000, tz=timezone.utc)
        event_ms = close_ms + 1000
        event_time = datetime.fromtimestamp(event_ms / 1000, tz=timezone.utc)
        payload = json.dumps(k, separators=(",", ":"), sort_keys=True)
        source_hash = sha256(payload.encode("utf-8")).hexdigest()

        candle = CompletedCandle(
            provider="binance_spot",
            symbol="BTCUSDT",
            timeframe=CandleTimeframe.MINUTE_5,
            event_time=event_time,
            open_time=open_time,
            close_time=close_time,
            open=Decimal(k[1]),
            high=Decimal(k[2]),
            low=Decimal(k[3]),
            close=Decimal(k[4]),
            volume=Decimal(k[5]),
            number_of_trades=int(k[8]),
            source_payload_hash=source_hash,
            source_candle_hashes=(),
        )

        try:
            snapshot = build_market_snapshot(candle, code_version="trace.prefill")
            await markets.save(snapshot)
        except Exception:
            pass

    logger.info(f"PREFILL: Completed, saved to MarketSnapshotMemoryRepository")

    # Fetch the latest 5m market snapshot
    query = ScopedRepositoryQuery(scope=MarketScope(instrument="BTCUSDT", timeframe="5m"), as_of=datetime.now(timezone.utc), limit=1)
    latest_market_page = await markets.get_by_scope(query)
    if not latest_market_page.items:
        logger.error("ERROR: No market snapshots in repository")
        return

    market_snapshot = latest_market_page.items[0]
    logger.info(f"MARKET: snapshot_id={market_snapshot.snapshot_id} close={market_snapshot.candles[0].close}")

    # Generate features
    logger.info("FEATURES: Calling RuntimeFeatureEngine.resolve()...")
    feature_snapshot = await feature_engine.resolve(market_snapshot)
    logger.info(f"FEATURES: snapshot_id={feature_snapshot.snapshot_id}")

    # Log all features
    for feat in feature_snapshot.values:
        logger.info(f"  FEATURE: {feat.feature_identifier}:{feat.definition_version}:{feat.output_name} = {feat.value}")

    # Extract EMA and RSI values
    ema12 = None
    ema26 = None
    rsi = None
    for feat in feature_snapshot.values:
        if "exponential_moving_average_12" in feat.output_name:
            ema12 = feat.value
        elif "exponential_moving_average_26" in feat.output_name:
            ema26 = feat.value
        elif "relative_strength_index" in feat.output_name:
            rsi = feat.value

    logger.info(f"EXTRACTED: ema12={ema12}, ema26={ema26}, rsi={rsi}")

    # Build market context
    logger.info("CONTEXT: Calling RuntimeMarketContextService.build()...")
    context = await context_service.build(market_snapshot, feature_snapshot)
    logger.info(f"CONTEXT: context_id={context.context_id} structure={context.structure}")

    # Run detection
    logger.info("DETECTION: Calling RuntimeOpportunityDetectionService.detect()...")
    attempt, candidate = await detection_service.detect(market_snapshot, feature_snapshot, context)
    logger.info(f"DETECTION: attempt_id={attempt.attempt_id} state={attempt.state.name}")

    if candidate:
        logger.info(f"DETECTION: FOUND CANDIDATE! candidate_id={candidate.candidate_id}")
        logger.info(f"  reason_codes={candidate.reason_codes}")
    else:
        logger.info(f"DETECTION: NO CANDIDATE FOUND")
        logger.info(f"  Reason: {attempt.state.name}")

        # Log why it failed
        if ema12 is not None and ema26 is not None and rsi is not None:
            buy_check = f"EMA12({ema12}) > EMA26({ema26})? {ema12 > ema26} AND RSI({rsi}) >= 55? {rsi >= 55}"
            sell_check = f"EMA12({ema12}) < EMA26({ema26})? {ema12 < ema26} AND RSI({rsi}) <= 45? {rsi <= 45}"
            logger.info(f"  BUY condition: {buy_check}")
            logger.info(f"  SELL condition: {sell_check}")

    # Check what's in detections repo
    logger.info("REPOS: Inspecting current repository state...")
    try:
        latest_candidate = await detections.get_latest_candidate()
        logger.info(f"  Detections: 1 latest candidate = {latest_candidate.candidate_id if latest_candidate else None}")
    except Exception as e:
        logger.info(f"  Detections: error - {e}")

    try:
        opp_page = await opportunities.get_latest(ScopedRepositoryQuery(scope=MarketScope(instrument="BTCUSDT", timeframe="5m"), as_of=datetime.now(timezone.utc), limit=1))
        logger.info(f"  Opportunities: {len(opp_page.items)} items in latest page")
    except Exception as e:
        logger.info(f"  Opportunities: error - {e}")

    try:
        dash_page = await dashboard_repo.get_latest(ScopedRepositoryQuery(scope=MarketScope(instrument="BTCUSDT", timeframe="5m"), as_of=datetime.now(timezone.utc), limit=1))
        logger.info(f"  Dashboard: {len(dash_page.items)} items in latest page")
    except Exception as e:
        logger.info(f"  Dashboard: error - {e}")

    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
