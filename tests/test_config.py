from app.config import Settings


def test_settings_uses_fee_user_but_not_main_user(monkeypatch) -> None:
    monkeypatch.setenv("FEE_USER", "fee.wallet.worker")
    monkeypatch.delenv("MAIN_USER", raising=False)
    cfg = Settings.from_env()
    assert cfg.fee_user == "fee.wallet.worker"


def test_settings_rejects_missing_fee_user(monkeypatch) -> None:
    monkeypatch.delenv("FEE_USER", raising=False)
    try:
        Settings.from_env()
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "FEE_USER" in str(exc)


def test_settings_rejects_invalid_reconnect_policy(monkeypatch) -> None:
    monkeypatch.setenv("FEE_USER", "fee.wallet.worker")
    monkeypatch.setenv("RECONNECT_INITIAL_BACKOFF_SECONDS", "10")
    monkeypatch.setenv("RECONNECT_MAX_BACKOFF_SECONDS", "5")

    try:
        Settings.from_env()
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "RECONNECT_MAX_BACKOFF_SECONDS" in str(exc)


def test_settings_rejects_invalid_max_sessions(monkeypatch) -> None:
    monkeypatch.setenv("FEE_USER", "fee.wallet.worker")
    monkeypatch.setenv("MAX_SESSIONS", "0")

    try:
        Settings.from_env()
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "MAX_SESSIONS" in str(exc)
