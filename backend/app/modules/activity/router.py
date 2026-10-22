from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.db import get_db
from app.modules.activity.models import ActivityLog
from app.modules.activity.schemas import ActivityOut
from app.modules.settings.models import User

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=list[ActivityOut])
def list_activity(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    """Newest first. Managers and owners only."""
    stmt = (
        select(ActivityLog, User.name)
        .join(User, User.id == ActivityLog.user_id, isouter=True)
        .where(ActivityLog.tenant_id == user.tenant_id)
        .order_by(ActivityLog.ts.desc(), ActivityLog.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        ActivityOut(
            id=row.id,
            ts=row.ts,
            user_id=row.user_id,
            user_name=name,
            role=row.role,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            details=row.details,
        )
        for row, name in db.execute(stmt)
    ]
