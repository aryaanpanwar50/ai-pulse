"""Track a completed diagnostic per organization membership.

Revision ID: 0002_diagnostic_submissions
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_diagnostic_submissions"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "diagnostic_submissions" not in tables:
        op.create_table(
            "diagnostic_submissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("membership_id", sa.Integer(), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"]),
            sa.UniqueConstraint("membership_id"),
        )

    inspector = inspect(bind)
    response_columns = {column["name"] for column in inspector.get_columns("responses")}
    if "submission_id" not in response_columns:
        with op.batch_alter_table("responses") as batch:
            batch.add_column(sa.Column("submission_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_responses_diagnostic_submission",
                "diagnostic_submissions",
                ["submission_id"],
                ["id"],
            )

    indexes = {index["name"] for index in inspect(bind).get_indexes("responses")}
    if "uq_response_submission_question" not in indexes:
        op.create_index(
            "uq_response_submission_question",
            "responses",
            ["submission_id", "question_id"],
            unique=True,
        )


def downgrade():
    bind = op.get_bind()
    indexes = {index["name"] for index in inspect(bind).get_indexes("responses")}
    if "uq_response_submission_question" in indexes:
        op.drop_index("uq_response_submission_question", table_name="responses")

    response_columns = {column["name"] for column in inspect(bind).get_columns("responses")}
    if "submission_id" in response_columns:
        with op.batch_alter_table("responses") as batch:
            batch.drop_column("submission_id")

    tables = set(inspect(bind).get_table_names())
    if "diagnostic_submissions" in tables:
        op.drop_table("diagnostic_submissions")
