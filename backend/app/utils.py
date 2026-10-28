ALLOWED_FLAGS = frozenset({
    "customer_data_shared",
    "confidential_data_shared",
    "unreviewed_output",
    "policy_unaware",
})


def maturity_level(avg_score):
    if avg_score is None:
        return "Not assessed"
    if avg_score < 2:
        return "Beginner"
    if avg_score < 3:
        return "Exploring"
    if avg_score < 4:
        return "Practitioner"
    return "Leader"
