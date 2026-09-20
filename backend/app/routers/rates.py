"""
Rates & the AQE Quote Engine.

POST /rates/quote is deliberately public (no auth) — it's what the website's
quote form calls before a visitor has any account. It doesn't touch the
database beyond reading active rates; the quote itself isn't persisted here
(that happens when the visitor submits POST /bookings/public with the
quoted price attached).

Duty percentages are a simple lookup rather than a table for now — matches
what the frontend prototype hardcoded, easy to move into its own table
later without changing the endpoint's shape.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.deps import CurrentUser, SessionDep, require_staff
from app.models import Rate
from app.schemas import RateCreate, RateRead, QuoteRequest, QuoteResponse

router = APIRouter(prefix="/rates", tags=["rates"])

# Fallback per-kg rates used when no matching Rate row exists in the database
# yet (e.g. a fresh install before rates.py has been seeded for every lane).
DEFAULT_PER_KG = {"sea": 1.85, "air": 4.20, "road": 2.10}

# Estimated destination-country customs duty, as a percentage. A real
# implementation would vary this by cargo category too — flagged here as a
# next step rather than baked in silently.
DUTY_BY_COUNTRY = {
    "the gambia": 14.0,
    "ghana": 16.0,
    "nigeria": 18.0,
    "senegal": 15.0,
    "sierra leone": 13.0,
}
DEFAULT_DUTY_PCT = 15.0


@router.get("", response_model=list[RateRead])
async def list_rates(session: SessionDep, user: CurrentUser):
    result = await session.exec(select(Rate).where(Rate.active == True))  # noqa: E712
    return result.all()


@router.post("", response_model=RateRead, dependencies=[Depends(require_staff())])
async def create_rate(body: RateCreate, session: SessionDep):
    rate = Rate(**body.model_dump())
    session.add(rate)
    await session.commit()
    await session.refresh(rate)
    return rate


@router.post("/quote", response_model=QuoteResponse)
async def get_quote(body: QuoteRequest, session: SessionDep):
    """No auth required — this is what a website visitor calls before they
    have any account. Looks for an active Rate matching the transport mode;
    falls back to DEFAULT_PER_KG if the database has no rate configured yet,
    so the quote engine still works on a freshly seeded database."""
    if body.weight_kg <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Weight must be greater than zero")

    result = await session.exec(
        select(Rate).where(Rate.transport_mode == body.transport_mode, Rate.active == True)  # noqa: E712
    )
    rate = result.first()
    price_per_kg = rate.price_per_kg if (rate and rate.price_per_kg) else DEFAULT_PER_KG[body.transport_mode.value]
    base_fee = rate.base_fee if (rate and rate.base_fee) else 0.0

    freight_cost = base_fee + (body.weight_kg * price_per_kg)
    duty_pct = DUTY_BY_COUNTRY.get(body.destination_country.strip().lower(), DEFAULT_DUTY_PCT)

    # Same rough declared-value estimate the frontend prototype used when the
    # visitor hasn't given one directly (kept obviously an estimate — this is
    # exactly the kind of thing that should get a warning label in the UI).
    declared_value = body.declared_value if body.declared_value else body.weight_kg * 8.0
    duty_estimate = declared_value * (duty_pct / 100)
    insurance_estimate = declared_value * 0.025 if body.add_insurance else 0.0

    total_estimate = freight_cost + duty_estimate + insurance_estimate
    quote_ref = "QT-" + (await _unique_code_suffix())

    return QuoteResponse(
        quote_ref=quote_ref,
        transport_mode=body.transport_mode,
        price_per_kg=price_per_kg,
        freight_cost=round(freight_cost, 2),
        duty_pct=duty_pct,
        duty_estimate=round(duty_estimate, 2),
        insurance_estimate=round(insurance_estimate, 2),
        total_estimate=round(total_estimate, 2),
    )


async def _unique_code_suffix() -> str:
    import random
    return str(random.randint(100000, 999999))
