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


def test_settings_fee_upstream_defaults_to_main_upstream(monkeypatch) -> None:
    monkeypatch.setenv("FEE_USER", "fee.wallet.worker")
    monkeypatch.setenv("UPSTREAM_HOST", "main.pool.local")
    monkeypatch.setenv("UPSTREAM_PRIMARY_PORT", "1234")
    monkeypatch.setenv("UPSTREAM_SECONDARY_PORT", "5678")
    monkeypatch.delenv("FEE_UPSTREAM_HOST", raising=False)
    monkeypatch.delenv("FEE_UPSTREAM_PRIMARY_PORT", raising=False)
    monkeypatch.delenv("FEE_UPSTREAM_SECONDARY_PORT", raising=False)

    cfg = Settings.from_env()
    assert cfg.fee_upstream_host == "main.pool.local"
    assert cfg.fee_upstream_primary_port == 1234
    assert cfg.fee_upstream_secondary_port == 5678


def test_settings_fee_upstream_can_be_overridden(monkeypatch) -> None:
    monkeypatch.setenv("FEE_USER", "fee.wallet.worker")
    monkeypatch.setenv("UPSTREAM_HOST", "main.pool.local")
    monkeypatch.setenv("FEE_UPSTREAM_HOST", "fee.pool.local")
    monkeypatch.setenv("FEE_UPSTREAM_PRIMARY_PORT", "3335")
    monkeypatch.setenv("FEE_UPSTREAM_SECONDARY_PORT", "4445")

    cfg = Settings.from_env()
    assert cfg.upstream_host == "main.pool.local"
    assert cfg.fee_upstream_host == "fee.pool.local"
    assert cfg.fee_upstream_primary_port == 3335
    assert cfg.fee_upstream_secondary_port == 4445


def test_settings_defaults_ratio_scope_and_startup_policy(monkeypatch) -> None:
    monkeypatch.setenv("FEE_USER", "fee.wallet.worker")
    monkeypatch.delenv("FEE_RATIO_SCOPE", raising=False)
    monkeypatch.delenv("FEE_PATH_STARTUP_POLICY", raising=False)

    cfg = Settings.from_env()

    assert cfg.fee_ratio_scope == "global"
    assert cfg.fee_path_startup_policy == "strict"


def test_settings_rejects_invalid_ratio_scope(monkeypatch) -> None:
    monkeypatch.setenv("FEE_USER", "fee.wallet.worker")
    monkeypatch.setenv("FEE_RATIO_SCOPE", "miner")

    try:
        Settings.from_env()
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "FEE_RATIO_SCOPE" in str(exc)


def test_settings_rejects_invalid_fee_startup_policy(monkeypatch) -> None:
    monkeypatch.setenv("FEE_USER", "fee.wallet.worker")
    monkeypatch.setenv("FEE_PATH_STARTUP_POLICY", "log_only")

    try:
        Settings.from_env()
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "FEE_PATH_STARTUP_POLICY" in str(exc)
