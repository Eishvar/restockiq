from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import current_user, require_role
from app.db import get_db
from app.modules.planning import service
from app.modules.planning.schemas import LinePatch, OrderOut, PlanCreate, PlanDetail, RejectBody, SendOut
from app.modules.settings.models import User

router = APIRouter(prefix="/planning", tags=["planning"])


@router.get("/context")
def context(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """What the Plan purchases page needs before anything is generated: today's date and the latest plan."""
    return service.context(db, user)


@router.post("/plans", response_model=PlanDetail, status_code=201)
def create_plan(body: PlanCreate, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    """Manager+: forecast, work out what to buy, and save one draft order per supplier."""
    run_id = service.generate_plan(db, user, body.horizon_days, body.today)
    return service.get_plan_detail(db, user, run_id)


@router.get("/plans/{run_id}", response_model=PlanDetail)
def get_plan(run_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.get_plan_detail(db, user, run_id)


@router.get("/orders", response_model=list[OrderOut])
def list_orders(status: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.list_orders(db, user, status)


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.get_order(db, user, order_id)


@router.patch("/orders/{order_id}/lines/{line_id}", response_model=OrderOut)
def edit_line(order_id: int, line_id: int, body: LinePatch, user: User = Depends(require_role("manager")),
              db: Session = Depends(get_db)):
    """Change how many packs to buy. Only while the order is still a draft."""
    return service.edit_line(db, user, order_id, line_id, body.final_packs)


@router.post("/orders/{order_id}/submit", response_model=OrderOut)
def submit(order_id: int, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    return service.submit(db, user, order_id)


@router.post("/orders/{order_id}/approve", response_model=OrderOut)
def approve(order_id: int, user: User = Depends(require_role("owner")), db: Session = Depends(get_db)):
    return service.approve(db, user, order_id)


@router.post("/orders/{order_id}/reject", response_model=OrderOut)
def reject(order_id: int, body: RejectBody, user: User = Depends(require_role("owner")), db: Session = Depends(get_db)):
    return service.reject(db, user, order_id, body.reason)


@router.post("/orders/{order_id}/send", response_model=SendOut)
def send(order_id: int, user: User = Depends(require_role("owner")), db: Session = Depends(get_db)):
    """Owner: mark an approved order as sent and get the WhatsApp message + link."""
    return service.send(db, user, order_id)


@router.post("/orders/{order_id}/receive", response_model=OrderOut)
def receive(order_id: int, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    """Manager+: the delivery arrived. Adds the packs to stock and sets the last-bought date."""
    return service.receive(db, user, order_id)
