from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.db import get_db
from app.modules.calendar import service
from app.modules.calendar.schemas import CalendarOut, EventIn, EventOut, EventPatch
from app.modules.planning import refresh
from app.modules.settings.models import User

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("", response_model=CalendarOut)
def list_events(user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    return service.list_events(db, user)


@router.post("", response_model=EventOut, status_code=201)
def add_event(body: EventIn, background: BackgroundTasks, user: User = Depends(require_role("manager")),
              db: Session = Depends(get_db)):
    event = service.add_event(db, user, body)
    background.add_task(refresh.run_recompute, user.tenant_id, user.id, "calendar")
    return event


@router.patch("/{event_id}", response_model=EventOut)
def edit_event(event_id: int, body: EventPatch, background: BackgroundTasks,
               user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    event = service.edit_event(db, user, event_id, body)
    background.add_task(refresh.run_recompute, user.tenant_id, user.id, "calendar")
    return event


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: int, background: BackgroundTasks, user: User = Depends(require_role("manager")),
                 db: Session = Depends(get_db)):
    service.delete_event(db, user, event_id)
    background.add_task(refresh.run_recompute, user.tenant_id, user.id, "calendar")


@router.post("/recompute")
def recompute(user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    """Re-measure forecast accuracy and safety buffers now (takes a few seconds)."""
    return service.recompute_now(db, user)
