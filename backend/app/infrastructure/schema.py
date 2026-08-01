"""Alembic schema-version validation for operational readiness."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.persistence.database import session_factory


def expected_schema_heads() -> frozenset[str]:
    """Return the immutable set of heads declared by the migration graph."""

    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    return frozenset(ScriptDirectory.from_config(config).get_heads())


async def current_schema_heads() -> frozenset[str]:
    """Read the database's applied Alembic heads without mutating schema."""

    async with session_factory() as session:
        rows = await session.execute(text("SELECT version_num FROM alembic_version"))
        return frozenset(str(value) for value in rows.scalars().all())


async def schema_is_current() -> bool:
    """Fail closed unless database and source migration heads match exactly."""

    return await current_schema_heads() == expected_schema_heads()
