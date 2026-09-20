"""
Auth dependencies. This is the part that directly replaces Postgres RLS —
in Supabase, "a courier can only see their assigned packages" lived in the
database as a policy. Here, that same rule has to be an explicit check in
every route that needs it. `require_role` and the helpers below are that
logic, centralized so each router just declares what it needs rather than
re-implementing checks inline.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import Profile, UserRole
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep,
) -> Profile:
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    profile = await session.get(Profile, user_id)
    if profile is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account no longer exists")
    return profile


CurrentUser = Annotated[Profile, Depends(get_current_user)]

STAFF_ROLES = {UserRole.admin, UserRole.chairman, UserRole.supervisor, UserRole.depot_staff}
ADMIN_ROLES = {UserRole.admin, UserRole.chairman}


def require_role(*allowed: UserRole):
    """Route dependency: `Depends(require_role(UserRole.admin))`. Raises 403
    if the current user's role isn't in the allowed set."""

    async def checker(user: CurrentUser) -> Profile:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted for your role")
        return user

    return checker


def require_staff():
    return require_role(*STAFF_ROLES)


def require_admin():
    """Stricter than require_staff() — for account management (creating,
    editing, or deleting staff logins) and anything else that shouldn't be
    open to every operational staff role, only admin/chairman."""
    return require_role(*ADMIN_ROLES)


async def get_by_id_or_404(session: AsyncSession, model, id: UUID):
    obj = await session.get(model, id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} not found")
    return obj


async def get_own_client_id(session: AsyncSession, user: Profile) -> UUID | None:
    """Resolves a logged-in client's Client.id from their Profile.id.

    Client accounts are two rows: the Profile (auth — email/password/role)
    and the Client (business record — client_code, shipments, invoices all
    point here via clients.id, not profiles.id). A client's Profile links
    to their Client row via Client.profile_id. Every 'show me my own
    shipments/bookings/invoices' filter needs this resolved id, not
    user.id directly — comparing Shipment.client_id (a clients.id) against
    user.id (a profiles.id) silently matches nothing."""
    from app.models import Client  # local import avoids a circular import with models.py
    result = await session.exec(select(Client).where(Client.profile_id == user.id))
    client = result.first()
    return client.id if client else None
