from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.agents.runtime import AgentUnavailable, get_agent_model
from app.auth import CurrentUser, assert_account_access, get_current_user
from app.db import get_db
from app.governance.breakers import BreakerOpen, ensure_closed
from app.knowledge.search import get_fund_search
from app.routers.accounts import account_or_404
from app.schemas.copilot import CopilotIn, CopilotOut
from app.services.devices import device_hash

router = APIRouter(prefix="/accounts", tags=["copilot"])
BUSY = "The copilot is busy right now; please try again in a minute."


@router.post("/{account_id}/copilot", response_model=CopilotOut)
def ask_copilot(account_id: str, body: CopilotIn, request: Request, db: Session = Depends(get_db), model=Depends(get_agent_model),
                search=Depends(get_fund_search), user: CurrentUser = Depends(get_current_user)):
    from app.agents.investor import answer_question

    account = account_or_404(db, account_id)
    assert_account_access(user, account)
    try:
        ensure_closed(db, "investor_copilot")
    except BreakerOpen as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    try:
        out = answer_question(db, account, body.question, [(t.role, t.text) for t in body.history], search, model,
                              device_hash=device_hash(request.headers.get("X-Device-Id")))
    except AgentUnavailable as e:
        raise HTTPException(status_code=503, detail=BUSY) from e
    db.commit()
    return out
