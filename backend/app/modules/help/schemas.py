from typing import Literal

from pydantic import BaseModel


class FaqItem(BaseModel):
    id: str
    topic: str
    question: str
    answer: str


class AskIn(BaseModel):
    question: str
    page: str = ""  # the screen the person is on, such as "/inventory"; helps the answer, never required


class AskOut(BaseModel):
    answer: str
    source: Literal["faq", "cache", "ai"]  # faq and cache cost nothing; only "ai" calls the model


class LlmHelpAnswer(BaseModel):
    """What the model must return (checked before anything is shown)."""

    answer: str
