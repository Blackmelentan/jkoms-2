"""One helper, called from wherever a sensitive action happens. Deliberately
tiny — commits its own row rather than trying to piggyback on the caller's
transaction, so a rollback elsewhere never silently erases the audit trail
of what was attempted."""

from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import AuditLog, Profile


async def log_audit(session: AsyncSession, actor: Profile, action: str, entity_type: str, entity_id: UUID | None, details: str = ""):
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_name=actor.full_name if actor else "system",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    session.add(entry)
    await session.commit()
