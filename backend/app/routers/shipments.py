"""
Shipments - the core lifecycle. The important design point here: updating
a shipment's stage happens through exactly ONE endpoint
(POST /{id}/events), which does two things in the same transaction:

  1. Inserts a row into journey_events (the permanent, append-only record
     of what happened, when, how, and by whom)
  2. Mirrors that stage onto shipments.current_stage (a fast-read cache of
     "what's the latest status" so list views don't have to aggregate
     journey_events every time)

There is no second way to change a shipment's status. That's what actually
prevents the double-entry problem the old build had - one write path, one
source of truth, current_stage is always derivable from journey_events and
never edited independently of it.
"""

from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.deps import CurrentUser, SessionDep, require_staff, get_by_id_or_404, get_own_client_id
from app.models import Shipment, Booking, JourneyEvent, UserRole, ShipmentStage, JourneyEventMethod
from app.schemas import (
    ShipmentCreate, ShipmentUpdate, ShipmentRead, ShipmentStageUpdate, CourierAssignRequest, JourneyEventRead
)
from app.utils import generate_tracking_code
from app.audit import log_audit

router = APIRouter(prefix="/shipments", tags=["shipments"])


async def _visibility_filter(query, user, session):
    if user.role in {UserRole.admin, UserRole.depot_staff, UserRole.chairman, UserRole.supervisor}:
        return query
    if user.role == UserRole.courier:
        return query.where(Shipment.assigned_courier_id == user.id)
    client_id = await get_own_client_id(session, user)
    if client_id is None:
        # A client-role login with no linked Client row yet — show nothing
        # rather than accidentally falling through to "everything".
        return query.where(Shipment.id == None)  # noqa: E711
    return query.where(Shipment.client_id == client_id)


@router.get("", response_model=list[ShipmentRead])
async def list_shipments(session: SessionDep, user: CurrentUser, search: str | None = None, stage: ShipmentStage | None = None):
    query = select(Shipment)
    query = await _visibility_filter(query, user, session)
    if stage:
        query = query.where(Shipment.current_stage == stage)
    if search:
        like = f"%{search}%"
        query = query.where((Shipment.tracking_code.ilike(like)) | (Shipment.recipient_name.ilike(like)))
    result = await session.exec(query.order_by(Shipment.created_at.desc()).limit(100))
    return result.all()


@router.get("/{shipment_id}", response_model=ShipmentRead)
async def get_shipment(shipment_id: UUID, session: SessionDep, user: CurrentUser):
    shipment = await get_by_id_or_404(session, Shipment, shipment_id)
    query = await _visibility_filter(select(Shipment).where(Shipment.id == shipment_id), user, session)
    visible = (await session.exec(query)).first()
    if visible is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted")
    return shipment


@router.post("", response_model=ShipmentRead, dependencies=[Depends(require_staff())])
async def create_shipment(body: ShipmentCreate, session: SessionDep, user: CurrentUser):
    tracking_code = await generate_tracking_code(session, Shipment)
    data = body.model_dump(exclude={"from_booking_id"})
    shipment = Shipment(**data, tracking_code=tracking_code, qr_payload=tracking_code, created_by=user.id)
    session.add(shipment)
    await session.flush()

    session.add(JourneyEvent(
        shipment_id=shipment.id,
        stage=ShipmentStage.booking,
        method=JourneyEventMethod.system,
        recorded_by=user.id,
        notes="Shipment created",
    ))

    if body.from_booking_id:
        booking = await session.get(Booking, body.from_booking_id)
        if booking:
            booking.status = "converted"
            booking.converted_shipment_id = shipment.id
            session.add(booking)

    await session.commit()
    await session.refresh(shipment)
    return shipment


@router.post("/{shipment_id}/events", response_model=ShipmentRead)
async def log_journey_event(shipment_id: UUID, body: ShipmentStageUpdate, session: SessionDep, user: CurrentUser):
    shipment = await get_by_id_or_404(session, Shipment, shipment_id)
    if user.role == UserRole.courier and shipment.assigned_courier_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not assigned to you")
    if user.role not in {UserRole.admin, UserRole.depot_staff, UserRole.chairman, UserRole.supervisor, UserRole.courier}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted")

    session.add(JourneyEvent(
        shipment_id=shipment.id,
        stage=body.stage,
        method=body.method,
        location_id=body.location_id,
        recorded_by=user.id,
        carrier_name=body.carrier_name,
        vehicle_ref=body.vehicle_ref,
        lat=body.lat,
        lng=body.lng,
        notes=body.notes,
    ))
    shipment.current_stage = body.stage
    shipment.updated_at = datetime.utcnow()
    session.add(shipment)
    await session.commit()
    await session.refresh(shipment)
    return shipment


@router.get("/{shipment_id}/events", response_model=list[JourneyEventRead])
async def get_shipment_events(shipment_id: UUID, session: SessionDep, user: CurrentUser):
    await get_shipment(shipment_id, session, user)
    result = await session.exec(
        select(JourneyEvent).where(JourneyEvent.shipment_id == shipment_id).order_by(JourneyEvent.occurred_at)
    )
    return result.all()


@router.patch("/{shipment_id}", response_model=ShipmentRead, dependencies=[Depends(require_staff())])
async def update_shipment(shipment_id: UUID, body: ShipmentUpdate, session: SessionDep, user: CurrentUser):
    """Admin/supervisor/depot_staff can correct any field on a shipment
    after it's been created — a package's weight, a vehicle's recipient
    details, an address typo, anything. Only fields actually present in the
    request body change; everything else is left alone. This does NOT
    touch current_stage — that only ever moves forward through
    POST /{id}/events, so the audit trail (journey_events) stays the single
    source of truth for 'what happened when', while this endpoint is purely
    for correcting the shipment's own details."""
    shipment = await get_by_id_or_404(session, Shipment, shipment_id)
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(shipment, field, value)
    session.add(shipment)
    await session.commit()
    await session.refresh(shipment)
    await log_audit(session, user, "shipment.update", "shipment", shipment.id, f"Changed {', '.join(changes.keys())} on {shipment.tracking_code}")
    return shipment


@router.patch("/{shipment_id}/courier", response_model=ShipmentRead, dependencies=[Depends(require_staff())])
async def assign_courier(shipment_id: UUID, body: CourierAssignRequest, session: SessionDep):
    shipment = await get_by_id_or_404(session, Shipment, shipment_id)
    shipment.assigned_courier_id = body.courier_id
    session.add(shipment)
    await session.commit()
    await session.refresh(shipment)
    return shipment


@router.post("/{shipment_id}/confirm-delivery", response_model=ShipmentRead)
async def confirm_delivery(shipment_id: UUID, session: SessionDep, user: CurrentUser):
    shipment = await get_by_id_or_404(session, Shipment, shipment_id)
    client_id = await get_own_client_id(session, user)
    if client_id is None or shipment.client_id != client_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your shipment")
    if shipment.current_stage != ShipmentStage.delivered:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Shipment isn't marked delivered yet")
    shipment.client_accepted = True
    shipment.client_accepted_at = datetime.utcnow()
    session.add(shipment)
    await session.commit()
    await session.refresh(shipment)
    return shipment
