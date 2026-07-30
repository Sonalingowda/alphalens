"""Application service connecting live data to append-only paper reports."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.paper_trading.market_data import PaperMarketDataService
from app.paper_trading.models import PaperTradingConfiguration
from app.persistence.paper_trading import (
    PersistedPaperTradingReport,
    persist_paper_trading_cycle,
)


class PaperTradingService:
    def __init__(
        self,
        market_data: PaperMarketDataService,
        configuration: PaperTradingConfiguration,
    ) -> None:
        self._market_data = market_data
        self._configuration = configuration

    async def run_cycle(
        self,
        session: AsyncSession,
        *,
        as_of: datetime,
    ) -> PersistedPaperTradingReport:
        snapshot = await self._market_data.fetch_completed_candles(
            as_of=as_of,
            history_observations=(
                self._configuration.market_history_observations
            ),
        )
        return await persist_paper_trading_cycle(
            session,
            snapshot=snapshot,
            configuration=self._configuration,
        )

