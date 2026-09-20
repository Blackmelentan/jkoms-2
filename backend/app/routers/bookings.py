from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlmodel import select

from app.deps import CurrentUser, SessionDep, require_staff, get_by_id_or_404, get_own_client_id
from app.models import Booking, UserRole
from app.schemas import BookingCreate, BookingRead, BookingReview
from app.utils import generate_booking_ref

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("/public", response_model=BookingRead)
async def create_public_booking(body: BookingCreate, session: SessionDep):
    """No auth required — this is what the public website's 'Book a
    Shipment' and AQE Quote Engine confirm step call. A website visitor has
    no account yet, so this can't sit behind the same auth as the staff
    booking list below. Everything it creates still lands in the exact same
    bookings table and shows up in Command Center's Bookings view."""
    booking = Booking(**body.model_dump(), booking_ref=await generate_booking_ref(session, Booking))
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    return booking


@router.get("", response_model=list[BookingRead])
async def list_bookings(session: SessionDep, user: CurrentUser):
    query = select(Booking)
    if user.role not in {UserRole.admin, UserRole.depot_staff, UserRole.chairman, UserRole.supervisor}:
        # Clients only ever see their own booking requests. Booking.client_id
        # is a clients.id, not a profiles.id — resolve the logged-in user's
        # linked Client row rather than comparing against user.id directly.
        client_id = await get_own_client_id(session, user)
        if client_id is None:
            query = query.where(Booking.id == None)  # noqa: E711 — no linked Client, show nothing
        else:
            query = query.where(Booking.client_id == client_id)
    result = await session.exec(query.order_by(Booking.created_at.desc()))
    return result.all()


@router.post("", response_model=BookingRead)
async def create_booking(body: BookingCreate, session: SessionDep, user: CurrentUser):
    booking = Booking(**body.model_dump(), booking_ref=await generate_booking_ref(session, Booking))
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    return booking


@router.patch("/{booking_id}/review", response_model=BookingRead, dependencies=[Depends(require_staff())])
async def review_booking(booking_id: UUID, body: BookingReview, session: SessionDep, user: CurrentUser):
    """Staff confirm/decline/quote a booking. Converting it into an actual
    shipment is a separate step (POST /shipments with from_booking_id) —
    kept separate so staff fill in the address/weight details a booking
    request doesn't capture before it becomes a trackable shipment."""
    booking = await get_by_id_or_404(session, Booking, booking_id)
    booking.status = body.status
    if body.quoted_price is not None:
        booking.quoted_price = body.quoted_price
        booking.quoted_currency = body.quoted_currency
    booking.reviewed_by = user.id
    booking.reviewed_at = datetime.utcnow()
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    return booking
