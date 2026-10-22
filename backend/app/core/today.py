"""The app's notion of "today" (the demo runs on a fixed date)."""
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.clock import now_kl
from app.modules.sales.models import SalesDaily


def get_today(db: Session, tenant_id: int) -> date:
    """env TODAY if set; else the day after the latest sales date; else the real date in Kuala Lumpur.

    (A per-tenant override in Settings is added in M8.)
    """
    if settings.today:
        return date.fromisoformat(settings.today)
    latest = db.scalar(select(func.max(SalesDaily.date)).where(SalesDaily.tenant_id == tenant_id))
    return latest + timedelta(days=1) if latest else now_kl().date()
