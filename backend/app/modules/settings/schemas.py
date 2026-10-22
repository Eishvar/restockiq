from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: str


class MeOut(UserOut):
    tenant_id: int
    tenant_name: str


# ---------- Settings (owner) ----------
RiskProfile = Literal["lean", "balanced", "never_run_out"]


class SupplierSettings(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    whatsapp: str
    min_order_rm: float
    delivery_days: str
    lead_time_days: int


class SettingsOut(BaseModel):
    tenant_name: str
    risk_profile: RiskProfile
    manual_planning_hours: float
    today_override: date | None
    today: date  # what the app is using as "today" right now
    # risk profile -> chance (0-1) that the safety buffer is enough, for [short life, medium life, long life] items
    service_levels: dict[str, list[float]]
    suppliers: list[SupplierSettings]
    buffers_updated_at: str | None


class SettingsPatch(BaseModel):
    """Only the fields that are sent are changed. `today_override: null` goes back to the real date."""

    risk_profile: RiskProfile | None = None
    manual_planning_hours: float | None = Field(default=None, gt=0, le=200)
    today_override: date | None = None


class SupplierPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    whatsapp: str | None = Field(default=None, max_length=30, pattern=r"^(\+?\d[\d \-]{6,20}\d)?$")
    min_order_rm: float | None = Field(default=None, ge=0, le=1_000_000)
