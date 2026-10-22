from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.activity import log_action
from app.core.auth import current_user, require_role
from app.db import get_db
from app.seed.load import reset_demo_data
from app.modules.settings.models import Tenant, User
from app.modules.settings.schemas import MeOut, UserOut

router = APIRouter(tags=["users"])


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    tenant = db.get(Tenant, user.tenant_id)
    return MeOut(id=user.id, name=user.name, role=user.role, tenant_id=user.tenant_id, tenant_name=tenant.name)


@router.post("/admin/reset")
def reset_demo(user: User = Depends(require_role("owner")), db: Session = Depends(get_db)):
    """Owner only: wipe the demo data and reload it from data/. Users stay, so nobody is signed out."""
    counts = reset_demo_data(db)
    log_action(db, user, "demo_data_reset", "tenant", user.tenant_id, {"rows": counts})
    db.commit()
    return {"status": "reset", "rows": counts}


@router.get("/users", response_model=list[UserOut])
def users(db: Session = Depends(get_db)):
    """Public on purpose: the simulated login screen lists who you can sign in as."""
    return db.scalars(select(User).order_by(User.id)).all()
