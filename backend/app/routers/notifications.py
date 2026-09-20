"""
Notifications log. This does NOT actually send an SMS or WhatsApp message —
there's no provider wired up yet (Africa's Talking, Twilio, WhatsApp
Business API, whichever gets picked). What it does do is give every other
part of the system one real place to log "we told the client X", which is
what the audit trail and de-duplication in the blueprint depend on. Wiring
an actual provider later means filling in `_dispatch()` below without
touching any of the callers.
"""

from fastapi import APIRouter, Depends
from sqlmodel import select

from app.deps import CurrentUser, SessionDep, require_staff
from app.models import NotificationLog, NotificationStatus
from app.schemas import NotificationCreate, NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
async def list_notifications(session: SessionDep, user: CurrentUser):
    result = await session.exec(select(NotificationLog).order_by(NotificationLog.sent_at.desc()))
    return result.all()


@router.post("", response_model=NotificationRead, dependencies=[Depends(require_staff())])
async def send_notification(body: NotificationCreate, session: SessionDep):
    status_ = _dispatch(body)
    log = NotificationLog(**body.model_dump(), status=status_)
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


def _dispatch(body: NotificationCreate) -> NotificationStatus:
    """Placeholder for the real SMS/WhatsApp provider call. Always
    'succeeds' locally so the rest of the system can be built and tested
    against a realistic notifications_log before a provider is chosen."""
    return NotificationStatus.sent
