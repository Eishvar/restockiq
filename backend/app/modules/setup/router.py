from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import current_user, require_role
from app.db import get_db
from app.modules.setup import service
from app.modules.setup.schemas import CompleteIn, CountryIn, CountryResult, SetupStatus
from app.modules.settings.models import User

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatus)
def get_status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Which wizard step comes next. Everyone can read it; only the owner can change it."""
    result = service.status(db, user.tenant_id)
    db.commit()  # status() creates the tenant's setup row the first time
    return result


@router.post("/country", response_model=CountryResult)
def choose_country(body: CountryIn, user: User = Depends(require_role("owner")), db: Session = Depends(get_db)):
    """Step 1. Malaysia sets the currency to MYR and loads the Malaysian public holidays."""
    return service.choose_country(db, user, body.country)


@router.post("/complete", response_model=SetupStatus)
def complete(body: CompleteIn, user: User = Depends(require_role("owner")), db: Session = Depends(get_db)):
    """Step 4 (optional calendar) done or skipped: the wizard is finished."""
    return service.complete(db, user, body.skip_calendar)
