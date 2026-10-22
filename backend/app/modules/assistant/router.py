from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai import llm
from app.core.auth import current_user, require_role
from app.db import get_db
from app.modules.assistant import service
from app.modules.assistant.schemas import (
    ApplyIn,
    ApplyOut,
    NoteIn,
    NoteOut,
    ShelfLifeIn,
    ShelfLifeOut,
    StatusOut,
)
from app.modules.settings.models import User

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/status", response_model=StatusOut)
def status(_: User = Depends(current_user)):
    """Is an AI provider configured? The screens show 'enter by hand' when it is not."""
    return StatusOut(available=llm.ai_available())


@router.post("/stock-note", response_model=NoteOut)
def stock_note(body: NoteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Read a messy stock note into rows to review. Saves nothing about your stock yet."""
    return service.parse_stock_note(db, user, body.note)


@router.post("/suggestions/{suggestion_id}/apply", response_model=ApplyOut)
def apply(suggestion_id: int, body: ApplyIn, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    """Manager+: save the (possibly edited) rows into stock."""
    return service.apply_stock_note(db, user, suggestion_id, body)


@router.post("/suggestions/{suggestion_id}/dismiss")
def dismiss(suggestion_id: int, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    return service.dismiss_suggestion(db, user, suggestion_id)


@router.post("/shelf-life", response_model=ShelfLifeOut)
def shelf_life(body: ShelfLifeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Suggest shelf life, storage and unit for a new item. A suggestion only; the person fills the form."""
    return service.suggest_shelf_life(db, user, body)
