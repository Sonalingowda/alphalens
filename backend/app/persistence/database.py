"""Async database engine and session factory."""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.settings import load_settings


settings = load_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
session_factory = async_sessionmaker(engine, expire_on_commit=False)
