"""Production startup validation executed before serving traffic."""

import argparse
import asyncio
import json

from sqlalchemy import text

from app.infrastructure.redis import RedisInfrastructure
from app.infrastructure.schema import schema_is_current
from app.inference.repository import load_production_artifact
from app.persistence.database import session_factory
from app.settings import load_settings


async def verify_readiness() -> dict[str, str]:
    """Verify database access and the immutable production artifact."""

    settings = load_settings()
    async with session_factory() as session:
        await session.execute(text("SELECT 1"))
        artifact = (
            await load_production_artifact(session)
            if settings.environment in {"staging", "production"}
            else None
        )
    redis = RedisInfrastructure.from_url(settings.redis_url)
    try:
        await redis.ping()
    finally:
        await redis.close()
    if not await schema_is_current():
        raise RuntimeError("Database schema is not at the current Alembic head.")
    result = {
        "status": "ready",
        "postgresql": "ready",
        "redis": "ready",
        "schema": "ready",
    }
    if artifact is not None:
        result["artifact_identifier"] = str(artifact.artifact_id)
        result["artifact_sha256"] = artifact.artifact_sha256
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "check",
        choices=("configuration", "readiness"),
    )
    arguments = parser.parse_args()
    settings = load_settings()
    if arguments.check == "configuration":
        result = {
            "status": "valid",
            "environment": settings.environment,
            "api_host": settings.host,
            "api_port": settings.port,
            "api_workers": settings.api_workers,
        }
    else:
        result = asyncio.run(verify_readiness())
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
