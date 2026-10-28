from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def alembic_config(db_url):
    config_path = Path(__file__).parents[1] / "alembic.ini"
    config = Config(str(config_path))
    config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))
    return config


def test_fresh_database_upgrades_to_head(tmp_path):
    database = tmp_path / "fresh.db"
    command.upgrade(alembic_config(f"sqlite:///{database.as_posix()}"), "head")

    engine = create_engine(f"sqlite:///{database.as_posix()}")
    inspector = inspect(engine)
    assert "diagnostic_submissions" in inspector.get_table_names()
    assert "submission_id" in {column["name"] for column in inspector.get_columns("responses")}
    assert {"feedback", "next_steps"} <= {column["name"] for column in inspector.get_columns("diagnostic_submissions")}
    assert any(index["name"] == "uq_response_submission_question" for index in inspector.get_indexes("responses"))
    engine.dispose()


def test_guidance_migration_preserves_existing_submissions(tmp_path):
    database = tmp_path / "before_guidance.db"
    url = f"sqlite:///{database.as_posix()}"
    config = alembic_config(url)
    command.upgrade(config, "0002_diagnostic_submissions")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO organizations (id, name) VALUES (1, 'Org')"))
        connection.execute(text("INSERT INTO users (id, email, name, password_hash) VALUES (1, 'u@test', 'User', 'hash')"))
        connection.execute(text("INSERT INTO memberships (id, user_id, org_id, role, job_role, seniority) VALUES (1, 1, 1, 'employee', 'support', 'junior')"))
        connection.execute(text("INSERT INTO diagnostic_submissions (id, membership_id, submitted_at) VALUES (1, 1, CURRENT_TIMESTAMP)"))
    engine.dispose()
    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT membership_id, feedback, next_steps FROM diagnostic_submissions")).one()
        assert row == (1, None, None)
    engine.dispose()


def test_legacy_responses_survive_versioned_upgrade(tmp_path):
    database = tmp_path / "legacy.db"
    url = f"sqlite:///{database.as_posix()}"
    config = alembic_config(url)
    command.upgrade(config, "0001_initial_schema")

    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO organizations (name) VALUES ('Northwind')"))
        connection.execute(text(
            "INSERT INTO users (email, name, password_hash) VALUES ('user@example.test', 'User', 'hash')"
        ))
        connection.execute(text(
            "INSERT INTO memberships (user_id, org_id, department_id, role, job_role, seniority) "
            "VALUES (1, 1, NULL, 'employee', 'support', 'junior')"
        ))
        connection.execute(text(
            "INSERT INTO responses (membership_id, question_id, answer, score, reason, flags, created_at) "
            "VALUES (1, 'common-freq', 'Daily', 4, NULL, '[]', CURRENT_TIMESTAMP)"
        ))
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.connect() as connection:
        row = connection.execute(text(
            "SELECT membership_id, question_id, submission_id FROM responses"
        )).one()
        assert row == (1, "common-freq", None)
    engine.dispose()


def test_existing_current_schema_can_be_stamped_then_upgraded(tmp_path):
    from app.db import Base
    from app import models  # noqa: F401

    database = tmp_path / "already_current.db"
    url = f"sqlite:///{database.as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    engine.dispose()

    config = alembic_config(url)
    command.stamp(config, "0001_initial_schema")
    command.upgrade(config, "head")

    engine = create_engine(url)
    assert "diagnostic_submissions" in inspect(engine).get_table_names()
    assert "submission_id" in {column["name"] for column in inspect(engine).get_columns("responses")}
    assert "average_score" in {column["name"] for column in inspect(engine).get_columns("diagnostic_submissions")}
    engine.dispose()


def test_submission_average_migration_backfills_only_linked_owned_scores(tmp_path):
    url = f"sqlite:///{(tmp_path / 'before_averages.db').as_posix()}"
    config = alembic_config(url)
    command.upgrade(config, "0003_personal_guidance")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO organizations (id, name) VALUES (1, 'Org')"))
        connection.execute(text("INSERT INTO users (id, email, name, password_hash) VALUES (1, 'u@test', 'User', 'hash')"))
        connection.execute(text("INSERT INTO memberships (id, user_id, org_id, role, job_role, seniority) VALUES (:id, 1, 1, 'employee', 'support', 'junior')"), [{"id": 1}, {"id": 2}])
        connection.execute(text("INSERT INTO diagnostic_submissions (id, membership_id, submitted_at, feedback) VALUES (:id, :id, CURRENT_TIMESTAMP, 'Saved feedback')"), [{"id": 1}, {"id": 2}])
        connection.execute(text(
            "INSERT INTO responses (membership_id, submission_id, question_id, answer, score, created_at) "
            "VALUES (:member, :submission, :question, 'Test', :score, CURRENT_TIMESTAMP)"
        ), [
            {"member": 1, "submission": 1, "question": "q1", "score": 1},
            {"member": 1, "submission": 1, "question": "q2", "score": 5},
            {"member": 1, "submission": 1, "question": "q3", "score": 4},
            {"member": 1, "submission": 1, "question": "q4", "score": None},
            {"member": 1, "submission": None, "question": "legacy", "score": 5},
            {"member": 2, "submission": 1, "question": "wrong-owner", "score": 5},
        ])
    engine.dispose()
    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT average_score, feedback FROM diagnostic_submissions ORDER BY id")).all()
        assert abs(rows[0][0] - 10 / 3) < 1e-10
        assert rows[0][1] == "Saved feedback"
        assert rows[1][0] is None
        assert connection.execute(text("SELECT COUNT(*) FROM responses")).scalar_one() == 6
    engine.dispose()
