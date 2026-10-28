from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..auth import current_membership
from ..db import get_db
from ..utils import maturity_level

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
MIN_RESPONDENTS = 5


@router.get("")
def org_dashboard(
    org_id: int,
    m: models.Membership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    if m.role != "admin":
        raise HTTPException(403, "Admins only")

    if org_id != m.org_id:
        raise HTTPException(403, "Cannot access this organization")

    org = db.get(models.Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    members = db.query(models.Membership).filter_by(org_id=org_id).all()
    submissions = (
        db.query(models.DiagnosticSubmission)
        .join(models.Membership, models.DiagnosticSubmission.membership_id == models.Membership.id)
        .filter(models.Membership.org_id == org_id)
        .all()
    )
    submission_by_member = {submission.membership_id: submission for submission in submissions}
    departments = []
    all_flags = {}
    risk_summary_available = False
    for dept in org.departments:
        dept_members = [member for member in members if member.department_id == dept.id]
        completed_members = [member for member in dept_members if member.id in submission_by_member]
        responded = len(completed_members)
        suppressed = responded < MIN_RESPONDENTS
        employee_averages = []
        if not suppressed:
            risk_summary_available = True

        # Suppressed teams contribute neither scores nor risks, including to
        # organization totals. Counts alone remain visible for participation.
        for member in completed_members if not suppressed else []:
            submission = submission_by_member[member.id]
            rows = (
                db.query(models.Response)
                .filter_by(
                    membership_id=member.id,
                    submission_id=submission.id,
                )
                .all()
            )
            employee_scores = []
            employee_flags = set()
            for response in rows:
                if response.score is not None:
                    employee_scores.append(response.score)
                employee_flags.update(response.flags or [])

            for flag in employee_flags:
                all_flags[flag] = all_flags.get(flag, 0) + 1

            if employee_scores:
                employee_averages.append(
                    sum(employee_scores) / len(employee_scores)
                )

        average = (
            sum(employee_averages) / len(employee_averages)
            if employee_averages
            else None
        )
        departments.append(
            {
                "department": dept.name,
                "employees": len(dept_members),
                "responded": responded,
                "suppressed": suppressed,
                "average_score": round(average, 2) if average is not None else None,
                "level": None if suppressed else maturity_level(average),
            }
        )

    return {
        "organization": org.name,
        "departments": departments,
        "minimum_respondents": MIN_RESPONDENTS,
        "risk_summary_available": risk_summary_available,
        "risk_summary_scope": "departments_meeting_minimum_responses",
        "top_risks": sorted(all_flags.items(), key=lambda item: (-item[1], item[0]))[:5],
    }
