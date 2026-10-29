from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..auth import current_membership
from ..db import get_db
from ..services.reporting import build_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/me")
def my_report(
    m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)
):
    submission = (
        db.query(models.DiagnosticSubmission).filter_by(membership_id=m.id).first()
    )
    if submission is None:
        raise HTTPException(404, "No submitted diagnostic report for this organization")

    responses = (
        db.query(models.Response)
        .filter_by(membership_id=m.id, submission_id=submission.id)
        .order_by(models.Response.id)
        .all()
    )
    return build_report(m, responses, submission)
