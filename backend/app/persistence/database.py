"""Async database engine and session factory."""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.settings import load_settings


settings = load_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout_seconds,
    pool_recycle=1_800,
)
session_factory = async_sessionmaker(engine, expire_on_commit=False)
