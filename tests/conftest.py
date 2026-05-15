"""Pytest fixtures для FRIDAY."""
import pytest
import os
import tempfile

import config
import database


@pytest.fixture(scope="function")
def test_db():
    """Каждый тест работает со своей временной БД."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    config.DB_PATH = db_path
    database.init_db()
    yield database
    # cleanup
    database.get_db().close()
    try:
        os.remove(db_path)
        os.rmdir(tmpdir)
    except OSError:
        pass
