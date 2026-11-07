import pytest
from fastapi.testclient import TestClient

from feature_signal.main import create_app

LUMEN_APP_ID = "c6c7bdd1-1010-4343-8b29-837a77793cab"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
