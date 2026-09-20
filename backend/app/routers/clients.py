from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.deps import CurrentUser, SessionDep, require_staff, get_by_id_or_404
from app.models import Client, UserRole
from app.schemas import ClientCreate, ClientRead
from app.utils import generate_client_code

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientRead], dependencies=[Depends(require_staff())])
async def list_clients(session: SessionDep, search: str | None = None):
    query = select(Client)
    if search:
        # Simple contains-match across the fields a staffer would actually
        # search by — client code, phone, or name.
        like = f"%{search}%"
        query = query.where(
            (Client.client_code.ilike(like)) | (Client.phone.ilike(like)) | (Client.full_name.ilike(like))
        )
    result = await session.exec(query.limit(20))
    return result.all()


@router.get("/me", response_model=ClientRead)
async def get_my_client_record(session: SessionDep, user: CurrentUser):
    """For a logged-in client account to fetch their own client_code/profile
    without needing staff permissions."""
    result = await session.exec(select(Client).where(Client.profile_id == user.id))
    client = result.first()
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No client record linked to this account")
    return client


@router.post("", response_model=ClientRead, dependencies=[Depends(require_staff())])
async def create_client(body: ClientCreate, session: SessionDep):
    client = Client(**body.model_dump(), client_code=await generate_client_code(session, Client))
    session.add(client)
    await session.commit()
    await session.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientRead)
async def get_client(client_id: UUID, session: SessionDep, user: CurrentUser):
    client = await get_by_id_or_404(session, Client, client_id)
    if user.role not in {UserRole.admin, UserRole.depot_staff, UserRole.chairman, UserRole.supervisor} and client.profile_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted")
    return client
