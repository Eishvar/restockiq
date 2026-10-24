from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Step = Literal["country", "pos", "inventory", "recipes", "calendar", "done"]


class SetupStatus(BaseModel):
    step: Step  # the first step not finished yet ("done" when the wizard is complete)
    complete: bool
    country: str | None
    country_name: str | None
    currency: str | None
    pos_provider: str | None
    pos_connected_at: datetime | None
    inventory_done: bool
    recipes_done: bool
    calendar_skipped: bool


class CountryIn(BaseModel):
    country: str


class CountryResult(BaseModel):
    status: SetupStatus
    holidays_added: int
    holidays_already_there: int


class CompleteIn(BaseModel):
    skip_calendar: bool = False
