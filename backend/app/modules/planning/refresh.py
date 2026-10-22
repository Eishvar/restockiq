"""Recompute safety buffers in the background (after a calendar change), without blocking the request."""
import logging
import threading

from app.core.activity import log_action
from app.db import SessionLocal
from app.modules.planning.quality import recompute_safety
from app.modules.settings.models import Tenant, User

log = logging.getLogger("restockiq.refresh")
_one_at_a_time = threading.Lock()  # two overlapping recomputes would delete and rewrite the same rows


def run_recompute(tenant_id: int, user_id: int, trigger: str) -> None:
    """Runs after the response is sent, in its own database session."""
    try:
        with _one_at_a_time, SessionLocal() as db:
            tenant, user = db.get(Tenant, tenant_id), db.get(User, user_id)
            summary = recompute_safety(db, tenant)
            log_action(db, user, "safety_recomputed", "tenant", tenant_id, {"trigger": trigger, **summary})
            db.commit()
    except Exception:  # a failed refresh must never take the server down; the old buffers stay in place
        log.exception("background recompute failed")
