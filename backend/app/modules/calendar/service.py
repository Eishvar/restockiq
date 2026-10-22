"""Business calendar: periods (semester, school holidays, Ramadan ...), public holidays and local events.

The forecaster reads this data, so a change here improves the next forecast straight away; the safety buffers
are re-measured in the background.
"""
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.activity import log_action
from app.core.today import get_today
from app.modules.calendar.models import CalendarEvent
from app.modules.calendar.schemas import CalendarOut, EventIn, EventOut, EventPatch
from app.modules.planning.models import SafetyProfile
from app.modules.planning.quality import recompute_safety
from app.modules.settings.models import Tenant, User

FIELDS = ("type", "label", "name", "start_date", "end_date")


def _snapshot(e: CalendarEvent) -> dict:
    return {f: (getattr(e, f).isoformat() if hasattr(getattr(e, f), "isoformat") else getattr(e, f)) for f in FIELDS}


def _event(db: Session, user: User, event_id: int) -> CalendarEvent:
    e = db.get(CalendarEvent, event_id)
    if e is None or e.tenant_id != user.tenant_id:
        raise HTTPException(404, "Calendar entry not found")
    return e


def list_events(db: Session, user: User) -> CalendarOut:
    events = list(
        db.scalars(select(CalendarEvent).where(CalendarEvent.tenant_id == user.tenant_id).order_by(CalendarEvent.start_date.desc(), CalendarEvent.id))
    )
    updated = db.scalar(select(func.max(SafetyProfile.computed_at)).where(SafetyProfile.tenant_id == user.tenant_id))
    return CalendarOut(
        today=get_today(db, user.tenant_id),
        events=[EventOut.model_validate(e, from_attributes=True) for e in events],
        labels=sorted({e.label for e in events if e.type == "period" and e.label}),
        buffers_updated_at=updated.isoformat() if updated else None,
    )


def add_event(db: Session, user: User, body: EventIn) -> EventOut:
    e = CalendarEvent(tenant_id=user.tenant_id, status="approved", source="manual", **body.model_dump())
    db.add(e)
    db.flush()
    log_action(db, user, "calendar_event_added", "calendar_event", e.id, _snapshot(e))
    db.commit()
    return EventOut.model_validate(e, from_attributes=True)


def edit_event(db: Session, user: User, event_id: int, body: EventPatch) -> EventOut:
    e = _event(db, user, event_id)
    before = _snapshot(e)
    for f in body.model_fields_set & set(FIELDS):
        value = getattr(body, f)
        if value is not None or f == "label":
            setattr(e, f, value)
    try:  # the merged entry must still make sense
        EventIn(type=e.type, label=e.label, name=e.name, start_date=e.start_date, end_date=e.end_date)
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(422, "; ".join(err["msg"].removeprefix("Value error, ") for err in exc.errors())) from None
    if e.type != "period":
        e.label = None
    e.source = "manual"
    after = _snapshot(e)
    if before != after:
        log_action(db, user, "calendar_event_edited", "calendar_event", e.id, {"before": before, "after": after})
    db.commit()
    return EventOut.model_validate(e, from_attributes=True)


def delete_event(db: Session, user: User, event_id: int) -> dict:
    e = _event(db, user, event_id)
    snap = _snapshot(e)
    db.delete(e)
    log_action(db, user, "calendar_event_deleted", "calendar_event", event_id, snap)
    db.commit()
    return snap


def recompute_now(db: Session, user: User) -> dict:
    """The 'Recompute' button: re-measure forecast accuracy and safety buffers, and wait for it."""
    summary = recompute_safety(db, db.get(Tenant, user.tenant_id))
    log_action(db, user, "safety_recomputed", "tenant", user.tenant_id, {"trigger": "manual", **summary})
    db.commit()
    return summary
