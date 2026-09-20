import random
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


async def _unique_code(session: AsyncSession, model, field_name: str, prefix: str) -> str:
    """Generates PREFIX-YYMM-XXXXXX, retrying on the rare collision. Used
    for tracking codes, booking refs, PO numbers — anything that needs a
    short human-speakable ID with a DB-level guarantee of uniqueness."""
    field = getattr(model, field_name)
    while True:
        now = datetime.utcnow()
        candidate = f"{prefix}-{now.strftime('%y%m')}-{random.randint(100000, 999999)}"
        existing = (await session.exec(select(model).where(field == candidate))).first()
        if existing is None:
            return candidate


async def generate_tracking_code(session: AsyncSession, model) -> str:
    return await _unique_code(session, model, "tracking_code", "JKG")


async def generate_booking_ref(session: AsyncSession, model) -> str:
    return await _unique_code(session, model, "booking_ref", "BK")


async def generate_client_code(session: AsyncSession, model) -> str:
    """Shorter format than tracking codes — this one gets read aloud to
    couriers and typed into checkout address fields, so brevity matters
    more than the date-encoding tracking codes have."""
    field = getattr(model, "client_code")
    while True:
        candidate = f"JKC-{random.randint(1000, 9999)}"
        existing = (await session.exec(select(model).where(field == candidate))).first()
        if existing is None:
            return candidate


async def generate_container_ref(session: AsyncSession, model) -> str:
    return await _unique_code(session, model, "container_number", "CTN")


async def generate_invoice_number(session: AsyncSession, model) -> str:
    return await _unique_code(session, model, "invoice_number", "INV")
