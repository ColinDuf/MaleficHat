import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

import create_db
import fonction_bdd

TEST_DB = root / "test_timezone.db"
create_db.DB_PATH = str(TEST_DB)
fonction_bdd.DB_PATH = str(TEST_DB)


def setup_module(module):
    if TEST_DB.exists():
        TEST_DB.unlink()
    create_db.create_db()


def teardown_module(module):
    if TEST_DB.exists():
        TEST_DB.unlink()


def test_default_timezone():
    assert fonction_bdd.get_reset_timezone(123) == "Europe/Paris"


def test_set_timezone():
    fonction_bdd.set_reset_timezone(123, "UTC")
    assert fonction_bdd.get_reset_timezone(123) == "UTC"
