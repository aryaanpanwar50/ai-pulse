from .. import models
from ..utils import maturity_level


def build_report(
    membership: models.Membership,
    responses: list[models.Response],
    submission: models.DiagnosticSubmission,
) -> dict:
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
        "feedback": submission.feedback,
        "next_steps": submission.next_steps or [],
    }
