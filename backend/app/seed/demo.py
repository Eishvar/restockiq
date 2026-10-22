"""Demo tenant and the three fictional users. M2's full seed loader reuses this."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.settings.models import Tenant, User

DEMO_TENANT_NAME = "Kopitiam Demo (AIMST)"
DEMO_USERS = [("Ah Hock", "owner"), ("Siti", "manager"), ("Ravi", "staff")]


def ensure_demo_tenant(db: Session) -> Tenant:
    """Create the demo tenant and users if no tenant exists yet (idempotent)."""
    tenant = db.scalars(select(Tenant).order_by(Tenant.id)).first()
    if tenant is None:
        tenant = Tenant(name=DEMO_TENANT_NAME, risk_profile="balanced", manual_planning_hours=16)
        db.add(tenant)
        db.flush()
        db.add_all(User(tenant_id=tenant.id, name=n, role=r) for n, r in DEMO_USERS)
        db.commit()
    return tenant
