import os
import pytest

@pytest.fixture(scope='session', autouse=True)
def clean_test_databases():
    for db in ('db_test.db', 'db_test_poland.db'):
        if os.path.exists(db):
            os.remove(db)
