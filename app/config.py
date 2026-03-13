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
    main_user: str = ""
    main_password: str = "x"
    fee_user: str = ""
    fee_password: str = "x"
    fee_ratio: float = 0.05
    metrics_host: str = "0.0.0.0"
    metrics_port: int = 9100

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
            main_user=os.getenv("MAIN_USER", ""),
            main_password=os.getenv("MAIN_PASSWORD", "x"),
            fee_user=os.getenv("FEE_USER", ""),
            fee_password=os.getenv("FEE_PASSWORD", "x"),
            fee_ratio=_env_float("FEE_RATIO", 0.05),
            metrics_host=os.getenv("METRICS_HOST", "0.0.0.0"),
            metrics_port=_env_int("METRICS_PORT", 9100),
        )
        if not (0 < cfg.fee_ratio < 1):
            raise ValueError("FEE_RATIO must be between 0 and 1")
        if not cfg.main_user:
            raise ValueError("MAIN_USER is required")
        if not cfg.fee_user:
            raise ValueError("FEE_USER is required")
        return cfg
