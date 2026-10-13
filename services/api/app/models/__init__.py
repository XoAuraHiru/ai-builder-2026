"""SQLAlchemy models. Importing this package registers every table on Base.metadata."""

from app.models.account import Account
from app.models.analysis import ANALYSIS_KINDS, Analysis
from app.models.ai_decision import AIDecision
from app.models.fund import FUND_CATEGORIES, Fund, FundConstituent
from app.models.instruction import (INSTRUCTION_STATES, INSTRUCTION_TYPES, STEP_STATES, Instruction, InstructionStep,
                                    RecurringPlan)
from app.models.operations import (ALERT_SEVERITIES, ALERT_STATES, APPROVAL_ACTIONS, APPROVAL_STATES, LINE_STATES,
                                   MATCH_STATES, MATCH_TIERS, AmlAlert, Approval, BankStatement, OpsRun, ReconMatch,
                                   StatementLine)
from app.models.lead import LEAD_SOURCES, LEAD_STAGES, IdentityCheck, Lead, LeadConversion
from app.models.ledger import INSTRUMENT_TYPES, POSTING_TYPES, Lot, Posting
from app.models.person import PERSON_KINDS, Person
from app.models.price import PRICE_STATUSES, Price
from app.models.proposal import Proposal
from app.models.risk_profile import RiskProfile
from app.models.trading import ORDER_SIDES, ORDER_STATES, ORDER_TYPES, VERDICTS, AccountDevice, TradeOrder, WatchItem

__all__ = [
    "AIDecision", "Account", "Analysis", "ANALYSIS_KINDS", "Fund", "FundConstituent", "FUND_CATEGORIES", "Instruction", "INSTRUCTION_STATES",
    "INSTRUCTION_TYPES", "InstructionStep", "RecurringPlan", "STEP_STATES", "IdentityCheck", "Lead", "LeadConversion", "LEAD_SOURCES", "LEAD_STAGES", "Lot", "Posting",
    "POSTING_TYPES", "INSTRUMENT_TYPES", "Person", "PERSON_KINDS", "Price", "PRICE_STATUSES", "Proposal", "RiskProfile",
    "AccountDevice", "ORDER_SIDES", "ORDER_STATES", "ORDER_TYPES", "TradeOrder", "VERDICTS", "WatchItem",
    "ALERT_SEVERITIES", "ALERT_STATES", "APPROVAL_ACTIONS", "APPROVAL_STATES", "AmlAlert", "Approval", "BankStatement",
    "LINE_STATES", "MATCH_STATES", "MATCH_TIERS", "OpsRun", "ReconMatch", "StatementLine",
]
