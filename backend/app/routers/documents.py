from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select

from app.deps import CurrentUser, SessionDep, require_staff
from app.models import Document
from app.schemas import DocumentCreate, DocumentRead

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    session: SessionDep,
    user: CurrentUser,
    related_type: str | None = None,
    related_id: UUID | None = None,
):
    query = select(Document)
    if related_type:
        query = query.where(Document.related_type == related_type)
    if related_id:
        query = query.where(Document.related_id == related_id)
    result = await session.exec(query.order_by(Document.created_at.desc()))
    return result.all()


@router.post("", response_model=DocumentRead, dependencies=[Depends(require_staff())])
async def create_document(body: DocumentCreate, session: SessionDep, user: CurrentUser):
    """Links a file already uploaded via POST /uploads to a shipment, booking,
    container, or client. Upload the file first, then call this with the
    URL it returns."""
    doc = Document(**body.model_dump(), uploaded_by=user.id)
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc
