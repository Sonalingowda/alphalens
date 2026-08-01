"""Container health probe for the policy-neutral background worker."""

from redis import Redis

from app.infrastructure.redis import RedisInfrastructure
from app.settings import load_settings


def main() -> None:
    settings = load_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        values = client.mget(
            tuple(
                f"{RedisInfrastructure.HEARTBEAT_PREFIX}worker.{index + 1}"
                for index in range(settings.worker_concurrency)
            )
        )
    finally:
        client.close()
    if not values or any(value != "alive" for value in values):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
