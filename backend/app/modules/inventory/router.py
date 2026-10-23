from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import current_user, require_role
from app.db import get_db
from app.modules.inventory import service
from app.modules.inventory.schemas import (
    BatchCreate,
    BatchPatch,
    DiscardResult,
    InventoryList,
    InventoryRow,
    ItemCreate,
    ItemPatch,
    MovementOut,
    OnboardingResult,
)
from app.modules.settings.models import User

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=InventoryList)
def get_inventory(user: User = Depends(current_user), db: Session = Depends(get_db)):
    today, onboarded, items = service.list_inventory(db, user)
    return InventoryList(today=today, onboarded=onboarded, items=items)


@router.post("/items", response_model=InventoryRow, status_code=201)
def add_item(body: ItemCreate, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    return service.add_item(db, user, body)


@router.post("/onboarding/confirm", response_model=OnboardingResult)
def confirm_onboarding(user: User = Depends(require_role("owner")), db: Session = Depends(get_db)):
    tenant = service.confirm_onboarding(db, user)
    return OnboardingResult(onboarded=True, onboarded_at=tenant.onboarded_at)


@router.post("/discard-expired", response_model=DiscardResult)
def discard_all_expired(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Throw away every expired batch at once (the 'Remove all expired' button)."""
    return service.discard_expired(db, user)


@router.patch("/batches/{batch_id}", response_model=InventoryRow)
def edit_batch(batch_id: int, body: BatchPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Staff may change the quantity only; managers and owners can also change date, shelf life and price."""
    return service.edit_batch(db, user, batch_id, body)


@router.delete("/batches/{batch_id}", status_code=204)
def remove_batch(batch_id: int, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    service.remove_batch(db, user, batch_id)


@router.post("/batches/{batch_id}/discard", response_model=DiscardResult)
def discard_batch(batch_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Throw away one expired batch."""
    return service.discard_batch(db, user, batch_id)


@router.patch("/{ingredient_id}", response_model=InventoryRow)
def edit_item(ingredient_id: int, body: ItemPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Staff may change the quantity only; managers and owners can also change dates, shelf life and price."""
    return service.edit_item(db, user, ingredient_id, body)


@router.delete("/{ingredient_id}", status_code=204)
def remove_item(ingredient_id: int, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    service.remove_item(db, user, ingredient_id)


@router.post("/{ingredient_id}/batches", response_model=InventoryRow, status_code=201)
def add_batch(ingredient_id: int, body: BatchCreate, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    """Record stock bought on one day as its own batch."""
    return service.add_batch(db, user, ingredient_id, body)


@router.post("/{ingredient_id}/discard-expired", response_model=DiscardResult)
def discard_one_expired(ingredient_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.discard_expired(db, user, ingredient_id)


@router.get("/{ingredient_id}/movements", response_model=list[MovementOut])
def item_movements(ingredient_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.movements(db, user, ingredient_id)
