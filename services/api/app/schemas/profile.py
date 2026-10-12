from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.risk_profile import PartialAnswers, RiskAnswers


class OptionOut(BaseModel):
    value: str | int
    label: str


class QuestionOut(BaseModel):
    key: str
    text: str
    options: list[OptionOut] | None


class RiskProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    band: int
    capacity_band: int
    tolerance_band: int
    answers: dict
    reasons: list[str]
    source: str


class RiskProfileState(BaseModel):
    current_band: int | None
    profile: RiskProfileOut | None
    questions: list[QuestionOut]


class SaveProfileIn(BaseModel):
    answers: RiskAnswers
    source: Literal["questionnaire", "conversation"] = "questionnaire"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=1000)


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=24)
    known: PartialAnswers = Field(default_factory=PartialAnswers)


class PreviewOut(BaseModel):
    band: int
    capacity_band: int
    tolerance_band: int
    reasons: list[str]


class ChatOut(BaseModel):
    reply: str
    answers: PartialAnswers
    missing: list[str]
    complete: bool
    preview: PreviewOut | None
