import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

import create_db
import fonction_bdd

TEST_DB = root / "test_recap.db"
create_db.DB_PATH = str(TEST_DB)
fonction_bdd.DB_PATH = str(TEST_DB)

def setup_module(module):
    if TEST_DB.exists():
        TEST_DB.unlink()
    create_db.create_db()

def teardown_module(module):
    if TEST_DB.exists():
        TEST_DB.unlink()

def test_default_recap_disabled():
    assert not fonction_bdd.is_recap_enabled(123, "daily")
    assert not fonction_bdd.is_recap_enabled(123, "weekly")

def test_enable_disable_recap():
    fonction_bdd.set_recap_mode(123, "daily", True)
    assert fonction_bdd.is_recap_enabled(123, "daily")
    fonction_bdd.set_recap_mode(123, "daily", False)
    assert not fonction_bdd.is_recap_enabled(123, "daily")
