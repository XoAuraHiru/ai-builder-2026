from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.llm import LLM, LLMError, get_llm
from app.auth import CurrentUser, get_current_user
from app.db import get_db
from app.models import Person
from app.schemas.profile import (ChatIn, ChatOut, OptionOut, PreviewOut, QuestionOut, RiskProfileOut,
                                 RiskProfileState, SaveProfileIn)
from app.services.risk_profile import QUESTIONS, chat_turn, latest_profile, save_profile

router = APIRouter(prefix="/me/risk-profile", tags=["profile"])
CHAT_BUSY = ("The conversation assistant is unavailable right now. Answer the five questions instead; it takes about "
             "a minute.")


def investor(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> Person:
    person = db.get(Person, user.person_id) if user.person_id else None
    if person is None or person.kind != "investor":
        raise HTTPException(status_code=403, detail="Risk profiles are for investors.")
    return person


def question_list() -> list[QuestionOut]:
    return [QuestionOut(key=key, text=q["text"],
                        options=None if q["options"] is None else [OptionOut(value=v, label=l) for v, l in q["options"]])
            for key, q in QUESTIONS.items()]


@router.get("", response_model=RiskProfileState)
def get_profile(person: Person = Depends(investor), db: Session = Depends(get_db)):
    latest = latest_profile(db, person.id)
    return RiskProfileState(current_band=person.risk_band, questions=question_list(),
                            profile=RiskProfileOut.model_validate(latest) if latest else None)


@router.post("", response_model=RiskProfileOut, status_code=201)
def save(body: SaveProfileIn, person: Person = Depends(investor), db: Session = Depends(get_db)):
    row = save_profile(db, person, body.answers, body.source)
    db.commit()
    return row


@router.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, person: Person = Depends(investor), db: Session = Depends(get_db),
         llm: LLM = Depends(get_llm)):
    try:
        turn = chat_turn(db, llm, person, [(m.role, m.text) for m in body.messages], body.known)
    except LLMError as e:
        raise HTTPException(status_code=503, detail=CHAT_BUSY) from e
    db.commit()
    return ChatOut(reply=turn.reply, answers=turn.answers, missing=turn.missing, complete=not turn.missing,
                   preview=PreviewOut(**asdict(turn.preview)) if turn.preview else None)
