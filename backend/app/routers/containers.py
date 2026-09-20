from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.deps import SessionDep, CurrentUser, require_staff, get_by_id_or_404
from app.models import Container, ContainerShipment, Shipment
from app.schemas import ContainerCreate, ContainerRead, ContainerStatusUpdate
from app.utils import generate_container_ref

router = APIRouter(prefix="/containers", tags=["containers"], dependencies=[Depends(require_staff())])


@router.get("", response_model=list[ContainerRead])
async def list_containers(session: SessionDep):
    result = await session.exec(select(Container).order_by(Container.created_at.desc()))
    return result.all()


@router.post("", response_model=ContainerRead)
async def create_container(body: ContainerCreate, session: SessionDep, user: CurrentUser):
    data = body.model_dump()
    if not data.get("container_number"):
        data["container_number"] = await generate_container_ref(session, Container)
    container = Container(**data, created_by=user.id)
    session.add(container)
    await session.commit()
    await session.refresh(container)
    return container


@router.patch("/{container_id}/status", response_model=ContainerRead)
async def update_container_status(container_id: UUID, body: ContainerStatusUpdate, session: SessionDep):
    container = await get_by_id_or_404(session, Container, container_id)
    container.status = body.status
    session.add(container)
    await session.commit()
    await session.refresh(container)
    return container


@router.post("/{container_id}/shipments/{shipment_id}")
async def add_shipment_to_container(container_id: UUID, shipment_id: UUID, session: SessionDep):
    await get_by_id_or_404(session, Container, container_id)
    await get_by_id_or_404(session, Shipment, shipment_id)
    existing = (await session.exec(
        select(ContainerShipment).where(
            ContainerShipment.container_id == container_id, ContainerShipment.shipment_id == shipment_id
        )
    )).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already in this container")
    session.add(ContainerShipment(container_id=container_id, shipment_id=shipment_id))
    await session.commit()
    return {"ok": True}


@router.delete("/{container_id}/shipments/{shipment_id}")
async def remove_shipment_from_container(container_id: UUID, shipment_id: UUID, session: SessionDep):
    link = (await session.exec(
        select(ContainerShipment).where(
            ContainerShipment.container_id == container_id, ContainerShipment.shipment_id == shipment_id
        )
    )).first()
    if link:
        await session.delete(link)
        await session.commit()
    return {"ok": True}
