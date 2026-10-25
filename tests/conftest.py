"""
Pytest configuration and test environment isolation.
Ensures unit tests run against local SQLite database and never execute destructive
cleanups against live production PostgreSQL instances.
"""

import os
import pytest

# Ensure PALLO_TEST_SQLITE is set for all tests
os.environ["PALLO_TEST_SQLITE"] = "1"

# Isolate tests from remote S3/Neon/R2 storage
for _k in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_ENDPOINT_URL_S3", "R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"]:
    os.environ.pop(_k, None)

@pytest.fixture(autouse=True)
def force_sqlite_for_tests(monkeypatch):
    monkeypatch.setenv("PALLO_TEST_SQLITE", "1")
    for k in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_ENDPOINT_URL_S3", "R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"]:
        monkeypatch.delenv(k, raising=False)
