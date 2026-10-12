from typing import Literal

from pydantic import BaseModel, Field


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=2000)


class CopilotIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    history: list[Turn] = Field(default_factory=list, max_length=8)


class TraceOut(BaseModel):
    tool: str
    label: str


class SourceOut(BaseModel):
    id: str
    title: str


class CopilotOut(BaseModel):
    answer: str
    trace: list[TraceOut]
    sources: list[SourceOut]
