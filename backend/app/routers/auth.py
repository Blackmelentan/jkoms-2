from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from app.deps import CurrentUser, SessionDep, require_staff, require_admin, get_by_id_or_404
from app.models import Profile
from app.schemas import TokenResponse, ChangePasswordRequest, ProfileCreate, ProfileRead, ProfileUpdate
from app.security import hash_password, verify_password, create_access_token
from app.audit import log_audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep):
    # OAuth2PasswordRequestForm uses `username` as the field name by spec —
    # we treat it as the email since that's how accounts are identified here.
    result = await session.exec(select(Profile).where(Profile.email == form.username))
    profile = result.first()
    if profile is None or not verify_password(form.password, profile.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    token = create_access_token(profile.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=ProfileRead)
async def get_me(user: CurrentUser):
    return user


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, user: CurrentUser, session: SessionDep):
    if len(body.new_password) < 8:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password must be at least 8 characters")
    user.hashed_password = hash_password(body.new_password)
    user.must_change_password = False
    session.add(user)
    await session.commit()
    return {"ok": True}


@router.post("/accounts", response_model=ProfileRead, dependencies=[Depends(require_admin())])
async def create_account(body: ProfileCreate, session: SessionDep, actor: CurrentUser):
    """Admin/chairman only — there's no public signup, matching the
    original app's model (accounts are provisioned by staff, not self-serve).
    The new account is forced to change its temporary password on first login."""
    existing = (await session.exec(select(Profile).where(Profile.email == body.email))).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "That email is already registered")
    profile = Profile(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
        phone=body.phone,
        location_id=body.location_id,
        must_change_password=True,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    await log_audit(session, actor, "account.create", "profile", profile.id, f"Created {profile.full_name} ({profile.role})")
    return profile


@router.get("/accounts", response_model=list[ProfileRead], dependencies=[Depends(require_staff())])
async def list_accounts(session: SessionDep):
    """Every account, any role — the full directory behind Command Center's
    Team page. (GET /staff?role=courier is a narrower, role-filtered version
    of this same list, used for pickers like courier assignment.)"""
    result = await session.exec(select(Profile).order_by(Profile.full_name))
    return result.all()


@router.patch("/accounts/{account_id}", response_model=ProfileRead, dependencies=[Depends(require_admin())])
async def update_account(account_id: UUID, body: ProfileUpdate, session: SessionDep, actor: CurrentUser):
    """Admin/chairman only. Editing someone's role, name, phone, depot
    assignment, or profile photo — never their password this way (that's
    /auth/change-password, and only the account owner can call it)."""
    profile = await get_by_id_or_404(session, Profile, account_id)
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(profile, field, value)
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    await log_audit(session, actor, "account.update", "profile", profile.id, f"Changed {', '.join(changes.keys())} on {profile.full_name}")
    return profile


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin())])
async def delete_account(account_id: UUID, session: SessionDep, user: CurrentUser):
    if account_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Can't delete your own account while logged in as it")
    profile = await get_by_id_or_404(session, Profile, account_id)
    name, role = profile.full_name, profile.role
    await session.delete(profile)
    await session.commit()
    await log_audit(session, user, "account.delete", "profile", account_id, f"Deleted {name} ({role})")
