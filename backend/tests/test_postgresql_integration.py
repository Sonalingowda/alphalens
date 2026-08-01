"""PostgreSQL repository parity tests enabled by integration environments."""

import os
from unittest import IsolatedAsyncioTestCase, skipUnless

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.opportunity_intelligence.persistence import (
    MarketSnapshotPostgreSQLRepository,
)
from app.opportunity_intelligence.repositories import EntityId
from app.persistence.database import engine, session_factory
from tests.test_opportunity_domain_models import _market_snapshot


@skipUnless(
    os.getenv("ALPHALENS_RUN_POSTGRES_TESTS") == "1",
    "PostgreSQL integration environment is not enabled.",
)
class PostgreSQLRepositoryIntegrationTests(IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        await engine.dispose()

    async def test_save_replay_read_and_database_immutability(self) -> None:
        repository = MarketSnapshotPostgreSQLRepository(session_factory)
        snapshot = _market_snapshot()

        self.assertEqual(await repository.save(snapshot), snapshot)
        self.assertEqual(await repository.save(snapshot), snapshot)
        restored = await repository.get_by_id(EntityId(snapshot.snapshot_id))

        self.assertEqual(restored, snapshot)
        self.assertEqual(restored.canonical_sha256(), snapshot.canonical_sha256())
        with self.assertRaises(SQLAlchemyError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE immutable_runtime_aggregates "
                        "SET revision = 2 WHERE entity_id = :entity_id"
                    ),
                    {"entity_id": snapshot.snapshot_id},
                )
