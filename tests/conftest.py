import pytest
import app.routes as routes
import app.auth.auth as auth
from app.routes import app as flask_app
from app.db.db import TEST_DB
from tests.test_db_setup import setup_test_db

@pytest.fixture(scope="session", autouse=True)
def force_test_database():
    """
    Make the app modules use the test database during test runs.
    """
    routes.DB_PATH = TEST_DB
    auth.DB_PATH = TEST_DB
    yield

@pytest.fixture
def client(setup_test_db):
    """
    Provide a Flask test client configured for the test database.

    The fixture enables request testing with the temporary
    database created by the setup_test_db fixture.

    :yield: Flask test client
    """
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client