"""
Staff directory. Currently just enough to power a courier picker when
assigning a shipment — GET /staff?role=courier — but shaped so it can also
back a real Team view later without changing the endpoint.
"""

from fastapi import APIRouter, Depends
from sqlmodel import select

from app.deps import SessionDep, require_staff, require_admin
from app.models import Profile, UserRole, AuditLog
from app.schemas import AuditLogRead

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("", dependencies=[Depends(require_staff())])
async def list_staff(session: SessionDep, role: UserRole | None = None):
    query = select(Profile)
    if role:
        query = query.where(Profile.role == role)
    result = await session.exec(query.order_by(Profile.full_name))
    profiles = result.all()
    # Hand-shaped response instead of a full schema — never leaks hashed_password.
    return [
        {"id": p.id, "full_name": p.full_name, "role": p.role, "location_id": p.location_id, "phone": p.phone}
        for p in profiles
    ]


@router.get("/audit-log", response_model=list[AuditLogRead], dependencies=[Depends(require_admin())])
async def list_audit_log(session: SessionDep, limit: int = 200):
    """Admin/chairman only. Newest first. Covers account create/edit/delete,
    shipment detail edits, and payments so far — see app/audit.py for how
    to extend coverage to more actions."""
    result = await session.exec(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
    return result.all()
