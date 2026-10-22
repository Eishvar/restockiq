from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db import get_db
from app.modules.settings.models import Tenant, User
from app.modules.settings.schemas import MeOut, UserOut

router = APIRouter(tags=["users"])


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    tenant = db.get(Tenant, user.tenant_id)
    return MeOut(id=user.id, name=user.name, role=user.role, tenant_id=user.tenant_id, tenant_name=tenant.name)


@router.get("/users", response_model=list[UserOut])
def users(db: Session = Depends(get_db)):
    """Public on purpose: the simulated login screen lists who you can sign in as."""
    return db.scalars(select(User).order_by(User.id)).all()
