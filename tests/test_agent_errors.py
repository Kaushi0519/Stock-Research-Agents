from unittest.mock import MagicMock

import anthropic

from src.agents.errors import (
    CREDIT_ALERT_STATE_KEY,
    alert_credit_exhausted,
    clear_credit_alert,
    is_insufficient_credit_error,
)
from src.storage.db import get_state_flag


def _fake_credit_error() -> MagicMock:
    exc = MagicMock(spec=anthropic.APIStatusError)
    exc.message = "Your credit balance is too low to access the Anthropic API."
    return exc


def test_detects_credit_balance_error():
    assert is_insufficient_credit_error(_fake_credit_error()) is True


def test_does_not_flag_other_api_status_errors():
    exc = MagicMock(spec=anthropic.APIStatusError)
    exc.message = "Rate limit exceeded, please try again later."
    assert is_insufficient_credit_error(exc) is False


def test_does_not_flag_non_api_errors():
    assert is_insufficient_credit_error(ValueError("some unrelated error")) is False


def test_alert_credit_exhausted_sends_once_then_suppresses(tmp_path, monkeypatch):
    import src.storage.db as db_module

    db_path = str(tmp_path / "test.db")
    db_module.init_db(db_path=db_path)
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    import src.agents.errors as errors_module
    monkeypatch.setattr(errors_module, "get_state_flag", lambda key: db_module.get_state_flag(key, db_path=db_path))
    monkeypatch.setattr(errors_module, "set_state_flag", lambda key, value: db_module.set_state_flag(key, value, db_path=db_path))

    notifier = MagicMock()

    alert_credit_exhausted(notifier)
    alert_credit_exhausted(notifier)  # second call within the same outage: must not re-send

    assert notifier.send.call_count == 1
    assert get_state_flag(CREDIT_ALERT_STATE_KEY, db_path=db_path) is True


def test_clear_credit_alert_rearms_it(tmp_path, monkeypatch):
    import src.storage.db as db_module

    db_path = str(tmp_path / "test.db")
    db_module.init_db(db_path=db_path)
    import src.agents.errors as errors_module
    monkeypatch.setattr(errors_module, "get_state_flag", lambda key: db_module.get_state_flag(key, db_path=db_path))
    monkeypatch.setattr(errors_module, "set_state_flag", lambda key, value: db_module.set_state_flag(key, value, db_path=db_path))

    notifier = MagicMock()

    alert_credit_exhausted(notifier)
    clear_credit_alert()
    alert_credit_exhausted(notifier)  # a fresh outage after recovery: should alert again

    assert notifier.send.call_count == 2
