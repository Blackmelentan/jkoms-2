"""
Payments. Recording one, of either method, updates the parent invoice's
status in the same transaction — this is what keeps "one ledger, online or
physical" true at the database level rather than as a UI convention.
"""

from fastapi import APIRouter, Depends
from sqlmodel import select, func

from app.deps import CurrentUser, SessionDep, require_staff, get_by_id_or_404
from app.models import Payment, Invoice, InvoiceStatus
from app.schemas import PaymentCreate, PaymentRead
from app.audit import log_audit

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("", response_model=list[PaymentRead])
async def list_payments(session: SessionDep, user: CurrentUser):
    result = await session.exec(select(Payment).order_by(Payment.paid_at.desc()))
    return result.all()


@router.post("", response_model=PaymentRead, dependencies=[Depends(require_staff())])
async def record_payment(body: PaymentCreate, session: SessionDep, user: CurrentUser):
    invoice = await get_by_id_or_404(session, Invoice, body.invoice_id)

    payment = Payment(**body.model_dump(), recorded_by=user.id)
    session.add(payment)
    await session.flush()  # so the paid-total query below sees this payment

    paid_total = (
        await session.exec(select(func.sum(Payment.amount)).where(Payment.invoice_id == invoice.id))
    ).one()
    paid_total = paid_total or 0.0

    if paid_total >= invoice.amount:
        invoice.status = InvoiceStatus.paid
    elif paid_total > 0:
        invoice.status = InvoiceStatus.partial
    session.add(invoice)

    await session.commit()
    await session.refresh(payment)
    await log_audit(session, user, "payment.record", "payment", payment.id, f"£{payment.amount:.2f} via {payment.method} against invoice {invoice.invoice_number}")
    return payment
