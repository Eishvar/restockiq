"""Owner settings. Every change is logged with before/after; a new risk profile recomputes the safety buffers."""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.activity import log_action
from app.core.today import get_today
from app.engine.safety import SERVICE_LEVELS
from app.modules.catalog.models import Supplier
from app.modules.planning.models import SafetyProfile
from app.modules.planning.quality import recompute_safety
from app.modules.settings.models import Tenant, User
from app.modules.settings.schemas import SettingsOut, SettingsPatch, SupplierPatch, SupplierSettings


def get_settings(db: Session, user: User) -> SettingsOut:
    tenant = db.get(Tenant, user.tenant_id)
    suppliers = db.scalars(select(Supplier).where(Supplier.tenant_id == user.tenant_id, Supplier.active.is_(True)).order_by(Supplier.name))
    updated = db.scalar(select(func.max(SafetyProfile.computed_at)).where(SafetyProfile.tenant_id == user.tenant_id))
    return SettingsOut(
        tenant_name=tenant.name,
        risk_profile=tenant.risk_profile,
        manual_planning_hours=tenant.manual_planning_hours,
        today_override=tenant.today_override,
        today=get_today(db, user.tenant_id),
        service_levels={k: list(v) for k, v in SERVICE_LEVELS.items()},
        suppliers=[SupplierSettings.model_validate(s) for s in suppliers],
        buffers_updated_at=updated.isoformat() if updated else None,
    )


def update_settings(db: Session, user: User, body: SettingsPatch) -> SettingsOut:
    tenant = db.get(Tenant, user.tenant_id)
    sent = body.model_fields_set
    before = {"risk_profile": tenant.risk_profile, "manual_planning_hours": tenant.manual_planning_hours,
              "today_override": tenant.today_override.isoformat() if tenant.today_override else None}
    if "risk_profile" in sent and body.risk_profile is not None:
        tenant.risk_profile = body.risk_profile
    if "manual_planning_hours" in sent and body.manual_planning_hours is not None:
        tenant.manual_planning_hours = body.manual_planning_hours
    if "today_override" in sent:
        tenant.today_override = body.today_override
    after = {"risk_profile": tenant.risk_profile, "manual_planning_hours": tenant.manual_planning_hours,
             "today_override": tenant.today_override.isoformat() if tenant.today_override else None}

    if before != after:
        log_action(db, user, "settings_changed", "tenant", tenant.id, {"before": before, "after": after})
        if before["risk_profile"] != after["risk_profile"]:
            # The service level behind every safety buffer depends on the risk profile, so measure again.
            summary = recompute_safety(db, tenant)
            log_action(db, user, "safety_recomputed", "tenant", tenant.id, {"trigger": "risk_profile", **summary})
    db.commit()
    return get_settings(db, user)


def update_supplier(db: Session, user: User, supplier_id: int, body: SupplierPatch) -> SupplierSettings:
    sup = db.get(Supplier, supplier_id)
    if sup is None or sup.tenant_id != user.tenant_id:
        raise HTTPException(404, "Supplier not found")
    fields = ("name", "whatsapp", "min_order_rm")
    before = {f: getattr(sup, f) for f in fields}
    for f in body.model_fields_set & set(fields):
        value = getattr(body, f)
        if value is not None:
            setattr(sup, f, value.strip() if isinstance(value, str) else value)
    after = {f: getattr(sup, f) for f in fields}
    if before != after:
        log_action(db, user, "supplier_updated", "supplier", sup.id, {"name": sup.name, "before": before, "after": after})
    db.commit()
    return SupplierSettings.model_validate(sup)
