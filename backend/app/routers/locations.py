from fastapi import APIRouter, Depends
from sqlmodel import select

from app.deps import CurrentUser, SessionDep, require_staff
from app.models import Location
from app.schemas import LocationCreate, LocationRead

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=list[LocationRead])
async def list_locations(session: SessionDep, user: CurrentUser):
    # Every authenticated role can read locations — needed for address
    # dropdowns, route displays, etc. across the whole app.
    result = await session.exec(select(Location))
    return result.all()


@router.post("", response_model=LocationRead, dependencies=[Depends(require_staff())])
async def create_location(body: LocationCreate, session: SessionDep):
    location = Location(**body.model_dump())
    session.add(location)
    await session.commit()
    await session.refresh(location)
    return location
