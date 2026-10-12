import math
import re

FEATURES = ["log_investable", "log_monthly", "horizon", "referral", "has_phone", "completeness", "goal_fit"]
LABELS = {"log_investable": "Investable assets", "log_monthly": "Monthly contribution",
          "horizon": "Investment horizon", "referral": "Came by referral", "has_phone": "Gave a valid phone number",
          "completeness": "Form completeness", "goal_fit": "Goals fit our fund range"}
PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def _filled(lead) -> list[bool]:
    return [bool(lead.phone), bool(lead.notes and len(lead.notes) >= 20), len(lead.goals or "") >= 20,
            lead.source_of_funds != "unspecified"]


def features_for(lead, enrichment: dict | None) -> dict[str, float]:
    filled = _filled(lead)
    return {
        "log_investable": math.log10(1 + float(lead.investable_usd)),
        "log_monthly": math.log10(1 + float(lead.monthly_usd)),
        "horizon": min(int(lead.horizon_years), 30) / 30,
        "referral": 1.0 if lead.source == "referral" else 0.0,
        "has_phone": 1.0 if lead.phone and PHONE_RE.match(lead.phone) else 0.0,
        "completeness": sum(filled) / len(filled),
        "goal_fit": 1.0 if enrichment and enrichment.get("suggested_funds") else 0.0,
    }


def describe(feature: str, lead) -> str:
    """The human-readable value shown next to a factor in the Why panel."""
    if feature == "log_investable":
        return f"${float(lead.investable_usd):,.0f}"
    if feature == "log_monthly":
        return f"${float(lead.monthly_usd):,.0f} a month"
    if feature == "horizon":
        return f"{lead.horizon_years} years"
    if feature == "completeness":
        return f"{round(100 * sum(_filled(lead)) / 4)}% of optional fields"
    if feature == "referral":
        return "yes" if lead.source == "referral" else f"no, came via {lead.source}"
    if feature == "has_phone":
        return "yes" if lead.phone and PHONE_RE.match(lead.phone) else "no"
    return ""
