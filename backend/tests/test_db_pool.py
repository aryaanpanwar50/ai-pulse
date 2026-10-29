from sqlalchemy.pool import QueuePool

from app.db import engine


def test_sqlite_reuses_one_connection_sequentially():
    assert isinstance(engine.pool, QueuePool)

    with engine.connect() as connection:
        first_driver_connection = connection.connection.driver_connection
    with engine.connect() as connection:
        second_driver_connection = connection.connection.driver_connection

    assert first_driver_connection is second_driver_connection
