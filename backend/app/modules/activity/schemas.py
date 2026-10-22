from datetime import datetime

from pydantic import BaseModel


class ActivityOut(BaseModel):
    id: int
    ts: datetime
    user_id: int | None
    user_name: str | None
    role: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    details: dict | None
