import importlib
import sys
from unittest.mock import patch
from pathlib import Path
import pytest

@pytest.fixture(scope="module")
def bot_module():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    if 'bot' in sys.modules:
        del sys.modules['bot']
    with patch("discord.Client.run"):
        module = importlib.import_module("bot")
    # Disable discord logging handler to avoid event loop access
    module.discord_handler.emit = lambda *a, **k: None
    return module


def test_lp_same_rank_and_tier(bot_module):
    assert bot_module.calculate_lp_change("IV", "GOLD", 50, "IV", "GOLD", 75) == 25


def test_lp_only_tier_changes(bot_module):
    assert bot_module.calculate_lp_change("III", "GOLD", 40, "II", "GOLD", 30) == 90


def test_lp_rank_changes(bot_module):
    assert bot_module.calculate_lp_change("II", "SILVER", 20, "IV", "GOLD", 80) == 260


def test_lp_invalid_values(bot_module):
    assert bot_module.calculate_lp_change("V", "GOLD", 50, "IV", "GOLD", 60) == 0
