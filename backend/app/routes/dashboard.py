from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..auth import current_membership
from ..db import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def level_for(avg):
    if avg is None:
        return "Not assessed"
    if avg < 1.5:
        return "Beginner"
    if avg < 2.5:
        return "Exploring"
    if avg < 3.5:
        return "Practitioner"
    return "Leader"


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
    departments = []
    all_flags = {}
    for dept in org.departments:
        dept_members = [member for member in members if member.department_id == dept.id]
        employee_averages = []
        responded = 0

        for member in dept_members:
            submission = (
                db.query(models.DiagnosticSubmission)
                .filter_by(membership_id=member.id)
                .first()
            )
            if submission is None:
                continue

            responded += 1
            rows = (
                db.query(models.Response)
                .filter_by(
                    membership_id=member.id,
                    submission_id=submission.id,
                )
                .all()
            )
            employee_scores = []
            for response in rows:
                if response.score is not None:
                    employee_scores.append(response.score)
                for flag in response.flags or []:
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
                "average_score": round(average, 2) if average is not None else None,
                "level": level_for(average),
            }
        )

    return {
        "organization": org.name,
        "departments": departments,
        "top_risks": sorted(all_flags.items(), key=lambda item: -item[1])[:5],
    }
