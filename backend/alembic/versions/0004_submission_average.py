"""Store and backfill the average score for each completed submission.

Revision ID: 0004_submission_average
Revises: 0003_personal_guidance
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_submission_average"
down_revision = "0003_personal_guidance"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("diagnostic_submissions")}
    if "average_score" not in columns:
        op.add_column("diagnostic_submissions", sa.Column("average_score", sa.Float(), nullable=True))

    submissions = sa.table(
        "diagnostic_submissions",
        sa.column("id", sa.Integer()),
        sa.column("membership_id", sa.Integer()),
        sa.column("average_score", sa.Float()),
    )
    responses = sa.table(
        "responses",
        sa.column("submission_id", sa.Integer()),
        sa.column("membership_id", sa.Integer()),
        sa.column("score", sa.Float()),
    )
    average = sa.select(sa.func.avg(responses.c.score)).where(
        responses.c.submission_id == submissions.c.id,
        responses.c.membership_id == submissions.c.membership_id,
    ).correlate(submissions).scalar_subquery()
    # AVG skips null scores. Legacy unlinked rows and wrong-owner rows are excluded.
    # Keep any already-saved snapshot when adopting an existing current schema.
    op.execute(submissions.update().where(submissions.c.average_score.is_(None)).values(average_score=average))


def downgrade():
    with op.batch_alter_table("diagnostic_submissions") as batch:
        batch.drop_column("average_score")
