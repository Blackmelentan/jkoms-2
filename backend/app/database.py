from collections.abc import AsyncGenerator

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from app.config import settings

# Async engine for the running app (FastAPI routes). Alembic migrations use
# a separate sync connection (see alembic/env.py) since Alembic's tooling
# doesn't support async drivers cleanly.
engine = create_async_engine(settings.database_url, echo=False, future=True)


async def init_db() -> None:
    """Create tables directly from models — convenient for first-run local
    dev. In any environment with real data, prefer `alembic upgrade head`
    instead so schema changes are tracked and reversible."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(engine) as session:
        yield session
