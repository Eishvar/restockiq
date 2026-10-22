from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

EventType = Literal["period", "public_holiday", "local_event"]


def clean_label(value: str | None) -> str | None:
    """'School Holidays ' -> 'school_holidays' so the forecaster groups the same label together."""
    if value is None:
        return None
    text = "_".join(value.strip().lower().split())
    return text or None


class EventIn(BaseModel):
    type: EventType
    label: str | None = Field(default=None, max_length=60)  # what the forecaster learns per; periods only
    name: str = Field(min_length=1, max_length=160)
    start_date: date
    end_date: date

    _label = field_validator("label")(clean_label)

    @model_validator(mode="after")
    def check(self):
        if self.end_date < self.start_date:
            raise ValueError("The end date cannot be before the start date")
        if self.type == "period" and not self.label:
            raise ValueError("A period needs a label, for example semester, break or school_holidays")
        if self.type != "period":
            self.label = None
        return self


class EventPatch(BaseModel):
    type: EventType | None = None
    label: str | None = Field(default=None, max_length=60)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    start_date: date | None = None
    end_date: date | None = None

    _label = field_validator("label")(clean_label)


class EventOut(BaseModel):
    id: int
    type: str
    label: str | None
    name: str
    start_date: date
    end_date: date
    status: str
    source: str


class CalendarOut(BaseModel):
    today: date
    events: list[EventOut]
    labels: list[str]  # period labels already in use, to suggest when adding
    buffers_updated_at: str | None
