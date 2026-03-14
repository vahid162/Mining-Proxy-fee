from __future__ import annotations

import os
from dataclasses import dataclass


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid float for {name}: {value}") from exc


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid int for {name}: {value}") from exc


@dataclass(frozen=True)
class Settings:
    listen_host: str = "0.0.0.0"
    listen_port: int = 40040
    socks5_host: str = "v2raya"
    socks5_port: int = 20170
    upstream_host: str = "bitcoin.viabtc.io"
    upstream_primary_port: int = 3333
    upstream_secondary_port: int = 443
    fee_upstream_host: str = "bitcoin.viabtc.io"
    fee_upstream_primary_port: int = 3333
    fee_upstream_secondary_port: int = 443
    main_password: str = "x"
    fee_user: str = ""
    fee_password: str = "x"
    fee_ratio: float = 0.05
    metrics_host: str = "0.0.0.0"
    metrics_port: int = 9100
    max_sessions: int = 500
    rpc_timeout_seconds: float = 15.0
    upstream_read_timeout_seconds: float = 120.0
    write_timeout_seconds: float = 10.0
    reconnect_initial_backoff_seconds: float = 1.0
    reconnect_max_backoff_seconds: float = 30.0
    reconnect_attempts: int = 0
    max_pending_rpcs: int = 256
    fee_ratio_scope: str = "global"
    fee_path_startup_policy: str = "strict"

    @classmethod
    def from_env(cls) -> "Settings":
        cfg = cls(
            listen_host=os.getenv("LISTEN_HOST", "0.0.0.0"),
            listen_port=_env_int("LISTEN_PORT", 40040),
            socks5_host=os.getenv("SOCKS5_HOST", "v2raya"),
            socks5_port=_env_int("SOCKS5_PORT", 20170),
            upstream_host=os.getenv("UPSTREAM_HOST", "bitcoin.viabtc.io"),
            upstream_primary_port=_env_int("UPSTREAM_PRIMARY_PORT", 3333),
            upstream_secondary_port=_env_int("UPSTREAM_SECONDARY_PORT", 443),
            fee_upstream_host=os.getenv("FEE_UPSTREAM_HOST", os.getenv("UPSTREAM_HOST", "bitcoin.viabtc.io")),
            fee_upstream_primary_port=_env_int("FEE_UPSTREAM_PRIMARY_PORT", _env_int("UPSTREAM_PRIMARY_PORT", 3333)),
            fee_upstream_secondary_port=_env_int("FEE_UPSTREAM_SECONDARY_PORT", _env_int("UPSTREAM_SECONDARY_PORT", 443)),
            main_password=os.getenv("MAIN_PASSWORD", "x"),
            fee_user=os.getenv("FEE_USER", ""),
            fee_password=os.getenv("FEE_PASSWORD", "x"),
            fee_ratio=_env_float("FEE_RATIO", 0.05),
            metrics_host=os.getenv("METRICS_HOST", "0.0.0.0"),
            metrics_port=_env_int("METRICS_PORT", 9100),
            max_sessions=_env_int("MAX_SESSIONS", 500),
            rpc_timeout_seconds=_env_float("RPC_TIMEOUT_SECONDS", 15.0),
            upstream_read_timeout_seconds=_env_float("UPSTREAM_READ_TIMEOUT_SECONDS", 120.0),
            write_timeout_seconds=_env_float("WRITE_TIMEOUT_SECONDS", 10.0),
            reconnect_initial_backoff_seconds=_env_float("RECONNECT_INITIAL_BACKOFF_SECONDS", 1.0),
            reconnect_max_backoff_seconds=_env_float("RECONNECT_MAX_BACKOFF_SECONDS", 30.0),
            reconnect_attempts=_env_int("RECONNECT_ATTEMPTS", 0),
            max_pending_rpcs=_env_int("MAX_PENDING_RPCS", 256),
            fee_ratio_scope=os.getenv("FEE_RATIO_SCOPE", "global"),
            fee_path_startup_policy=os.getenv("FEE_PATH_STARTUP_POLICY", "strict"),
        )
        if not (0 < cfg.fee_ratio < 1):
            raise ValueError("FEE_RATIO must be between 0 and 1")
        if not cfg.fee_user:
            raise ValueError("FEE_USER is required")
        if cfg.max_sessions < 1:
            raise ValueError("MAX_SESSIONS must be >= 1")
        if cfg.rpc_timeout_seconds <= 0:
            raise ValueError("RPC_TIMEOUT_SECONDS must be > 0")
        if cfg.upstream_read_timeout_seconds <= 0:
            raise ValueError("UPSTREAM_READ_TIMEOUT_SECONDS must be > 0")
        if cfg.write_timeout_seconds <= 0:
            raise ValueError("WRITE_TIMEOUT_SECONDS must be > 0")
        if cfg.reconnect_initial_backoff_seconds <= 0:
            raise ValueError("RECONNECT_INITIAL_BACKOFF_SECONDS must be > 0")
        if cfg.reconnect_max_backoff_seconds < cfg.reconnect_initial_backoff_seconds:
            raise ValueError("RECONNECT_MAX_BACKOFF_SECONDS must be >= RECONNECT_INITIAL_BACKOFF_SECONDS")
        if cfg.reconnect_attempts < 0:
            raise ValueError("RECONNECT_ATTEMPTS must be >= 0")
        if cfg.max_pending_rpcs < 1:
            raise ValueError("MAX_PENDING_RPCS must be >= 1")
        if cfg.fee_ratio_scope not in {"global", "session"}:
            raise ValueError("FEE_RATIO_SCOPE must be one of: global, session")
        if cfg.fee_path_startup_policy not in {"strict", "best_effort"}:
            raise ValueError("FEE_PATH_STARTUP_POLICY must be one of: strict, best_effort")
        return cfg
