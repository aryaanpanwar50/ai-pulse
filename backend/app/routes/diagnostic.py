import math
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..auth import current_membership
from ..db import get_db
from ..services.questions import load_questions, questions_for
from ..services.scoring import score_open_answer
from ..utils import ALLOWED_FLAGS

router = APIRouter(prefix="/diagnostic", tags=["diagnostic"])


class AnswerIn(BaseModel):
    question_id: str
    answer: str


class SubmitIn(BaseModel):
    answers: list[AnswerIn]


@router.get("/questions")
def get_questions(m: models.Membership = Depends(current_membership)):
    qs = questions_for(m.job_role, m.seniority)
    # don't leak scoring points to the client
    return [
        {k: v for k, v in q.items() if k != "points"}
        | ({"options": [o["text"] for o in q["options"]]} if q["type"] == "mcq" else {})
        for q in qs
    ]


@router.post("/submit")
def submit(
    body: SubmitIn,
    m: models.Membership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    if db.query(models.DiagnosticSubmission).filter_by(membership_id=m.id).first():
        raise HTTPException(
            409, "A diagnostic is already submitted for this organization"
        )

    assigned_questions = questions_for(m.job_role, m.seniority)
    assigned = {q["id"]: q for q in assigned_questions}
    answer_ids = [answer.question_id for answer in body.answers]
    if len(answer_ids) != len(set(answer_ids)):
        raise HTTPException(400, "Each question must be answered exactly once")

    supplied = set(answer_ids)
    expected = set(assigned)
    unknown = supplied - expected
    missing = expected - supplied
    if unknown:
        raise HTTPException(
            400, f"Questions not assigned to you: {', '.join(sorted(unknown))}"
        )
    if missing:
        raise HTTPException(
            400, f"Please answer every question: {', '.join(sorted(missing))}"
        )

    scored_answers = []
    for answer in body.answers:
        if not answer.answer.strip():
            raise HTTPException(400, f"Answer for {answer.question_id} cannot be empty")
        question = assigned[answer.question_id]
        response = {
            "membership_id": m.id,
            "question_id": question["id"],
            "answer": answer.answer,
            "score": None,
            "reason": None,
            "flags": [],
        }
        if question["type"] == "mcq":
            option = next(
                (o for o in question["options"] if o["text"] == answer.answer), None
            )
            if option is None:
                raise HTTPException(400, f"Invalid option for {question['id']}")
            response["score"] = option["points"]
        else:
            try:
                result = score_open_answer(question["text"], answer.answer)
            except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError):
                raise HTTPException(
                    502, "AI scoring failed; no answers were saved"
                ) from None
            score = result.get("score")
            reason = result.get("reason")
            flags = result.get("flags", [])
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
                or not 1 <= score <= 5
            ):
                raise HTTPException(
                    502, "AI scoring returned an invalid score; no answers were saved"
                )
            if (
                not isinstance(reason, str)
                or not isinstance(flags, list)
                or any(
                    not isinstance(flag, str) or flag not in ALLOWED_FLAGS
                    for flag in flags
                )
            ):
                raise HTTPException(
                    502, "AI scoring returned invalid details; no answers were saved"
                )
            response["score"] = float(score)
            response["reason"] = reason
            response["flags"] = flags
        scored_answers.append(response)

    submission = models.DiagnosticSubmission(
        membership_id=m.id,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(submission)
    try:
        db.flush()
        for response in scored_answers:
            db.add(
                models.Response(
                    membership_id=m.id,
                    submission_id=submission.id,
                    question_id=response["question_id"],
                    answer=response["answer"],
                    score=response["score"],
                    reason=response["reason"],
                    flags=response["flags"],
                )
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "A diagnostic is already submitted for this organization"
        ) from None

    return {"submitted": True, "submitted_at": submission.submitted_at}


@router.get("/me")
def my_diagnostic(
    m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)
):
    submission = (
        db.query(models.DiagnosticSubmission).filter_by(membership_id=m.id).first()
    )
    return {
        "submitted": submission is not None,
        "submitted_at": submission.submitted_at if submission else None,
    }


@router.delete("/me")
def delete_my_diagnostic(
    m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)
):
    """Delete this selected organization's response and its derived report."""
    deleted_answers = (
        db.query(models.Response)
        .filter_by(membership_id=m.id)
        .delete(synchronize_session=False)
    )
    deleted_submissions = (
        db.query(models.DiagnosticSubmission)
        .filter_by(membership_id=m.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {
        "deleted_answers": deleted_answers,
        "deleted_submissions": deleted_submissions,
    }
