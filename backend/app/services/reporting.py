from .. import models
from ..utils import maturity_level


NEXT_STEPS = {
    "support": ["Use AI to draft first replies, then edit", "Summarise long ticket threads before escalating", "Never paste customer details into public chatbots"],
    "engineering": ["Use a code assistant for tests and refactors", "Review every AI suggestion before merging", "Keep secrets and customer data out of prompts"],
    "sales": ["Draft outreach emails with AI and personalise them", "Summarise call notes into CRM updates", "Check AI-written claims before sending"],
    "manager": ["Agree an AI usage policy with your team", "Pick one workflow per quarter to improve with AI", "Track time saved, not tool licences"],
}


def build_report(membership: models.Membership, responses: list[models.Response]) -> dict:
    scores = [response.score for response in responses if response.score is not None]
    average = sum(scores) / len(scores) if scores else None
    risks = sorted({flag for response in responses for flag in (response.flags or [])})
    return {
        "name": membership.user.name,
        "organization": membership.org.name,
        "answered": len(responses),
        "average_score": round(average, 2) if average is not None else None,
        "level": maturity_level(average),
        "risks": risks,
        "next_steps": NEXT_STEPS.get(membership.job_role, NEXT_STEPS["manager"]),
    }
