from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select

from app.deps import CurrentUser, SessionDep, require_staff, get_by_id_or_404, get_own_client_id
from app.models import Invoice, UserRole
from app.schemas import InvoiceCreate, InvoiceRead
from app.utils import generate_invoice_number

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=list[InvoiceRead])
async def list_invoices(session: SessionDep, user: CurrentUser):
    query = select(Invoice)
    if user.role not in {UserRole.admin, UserRole.depot_staff, UserRole.chairman, UserRole.supervisor, UserRole.customs_finance}:
        # Clients only see their own invoices. Invoice.client_id is a
        # clients.id, not a profiles.id, so it has to be resolved via the
        # logged-in user's linked Client row — see get_own_client_id's
        # docstring for why comparing straight against user.id is wrong.
        client_id = await get_own_client_id(session, user)
        if client_id is None:
            query = query.where(Invoice.id == None)  # noqa: E711 — no linked Client, show nothing
        else:
            query = query.where(Invoice.client_id == client_id)
    result = await session.exec(query.order_by(Invoice.issued_at.desc()))
    return result.all()


@router.get("/{invoice_id}", response_model=InvoiceRead)
async def get_invoice(invoice_id: UUID, session: SessionDep, user: CurrentUser):
    return await get_by_id_or_404(session, Invoice, invoice_id)


@router.post("", response_model=InvoiceRead, dependencies=[Depends(require_staff())])
async def create_invoice(body: InvoiceCreate, session: SessionDep):
    invoice = Invoice(**body.model_dump(), invoice_number=await generate_invoice_number(session, Invoice))
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)
    return invoice
