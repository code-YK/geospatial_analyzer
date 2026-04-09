"""
api/dependencies.py — FastAPI dependencies (DB session, auth placeholder).
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async database session for use in FastAPI route dependencies.

    Usage:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user() -> dict:
    """
    Placeholder authentication dependency.

    Replace with a real authentication mechanism in production.
    """
    return {"user_id": "anonymous", "role": "user"}
