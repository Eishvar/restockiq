"""Activity (audit) log. Every consequential action calls log_action()."""
from sqlalchemy.orm import Session

from app.core.clock import now_kl
from app.modules.activity.models import ActivityLog
from app.modules.settings.models import User


def log_action(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | str | None = None,
    details: dict | None = None,
    tenant_id: int | None = None,
) -> ActivityLog:
    """Add one row to the activity log in the caller's transaction (the caller commits).

    `tenant_id` is only needed for system actions with no user (e.g. the nightly job).
    """
    tid = user.tenant_id if user is not None else tenant_id
    if tid is None:
        raise ValueError("log_action needs a user or a tenant_id")
    row = ActivityLog(
        tenant_id=tid,
        ts=now_kl(),
        user_id=user.id if user is not None else None,
        role=user.role if user is not None else None,
        action=action,
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id),
        details=details,
    )
    db.add(row)
    db.flush()
    return row
