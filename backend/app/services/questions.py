import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "questions.json")
_SENIORITY_RANK = {"junior": 0, "mid": 1, "senior": 2, "lead": 3}


def load_questions():
    with open(_PATH) as f:
        return json.load(f)


def questions_for(job_role: str, seniority: str):
    """Common questions for everyone + questions for this job role, filtered by seniority."""
    result = []
    seniority_rank = _SENIORITY_RANK.get(seniority, -1)
    for q in load_questions():
        if q["roles"] != ["all"] and job_role not in q["roles"]:
            continue
        minimum_rank = _SENIORITY_RANK.get(q.get("min_seniority", "junior"), 0)
        if seniority_rank < minimum_rank:
            continue
        result.append(q)
    return result
