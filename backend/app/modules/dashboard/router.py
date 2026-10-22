from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db import get_db
from app.modules.dashboard import service
from app.modules.dashboard.schemas import DashboardOut
from app.modules.settings.models import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.dashboard(db, user)
