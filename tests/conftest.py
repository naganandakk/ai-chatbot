import base64

import pytest

from tests.support import TEST_SECRET

TEST_KEY_ENCRYPTION_KEY = base64.b64encode(bytes(range(32))).decode()


@pytest.fixture(autouse=True)
def app_environment(monkeypatch):
    # create_app() reads these when no AuthConfig is passed
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
    monkeypatch.setenv("KEY_ENCRYPTION_KEYS", TEST_KEY_ENCRYPTION_KEY)
    # Rate limits would trip during tests that send many requests; they have their own test
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
