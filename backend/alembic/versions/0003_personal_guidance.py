"""Store submission-time personalized guidance.

Revision ID: 0003_personal_guidance
Revises: 0002_diagnostic_submissions
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_personal_guidance"
down_revision = "0002_diagnostic_submissions"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("diagnostic_submissions")}
    if "feedback" not in columns:
        op.add_column("diagnostic_submissions", sa.Column("feedback", sa.Text(), nullable=True))
    if "next_steps" not in columns:
        op.add_column("diagnostic_submissions", sa.Column("next_steps", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("diagnostic_submissions") as batch:
        batch.drop_column("next_steps")
        batch.drop_column("feedback")
