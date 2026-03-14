import asyncio

from app.config import Settings
from app.fee import FeeController, RatioTracker
from app.proxy import MinerMetrics, MinerProxy


async def _exercise_global_ratio_scope() -> None:
    cfg = Settings(fee_user="fee.wallet.worker", fee_ratio=0.5, fee_ratio_scope="global")
    proxy = MinerProxy(cfg, MinerMetrics())
    controller = FeeController(cfg.fee_ratio)

    first = await proxy._select_path(controller, RatioTracker())
    assert first == "fee"

    await proxy._record_accepted("fee", 10.0, RatioTracker())
    second = await proxy._select_path(controller, RatioTracker())
    assert second == "main"


async def _exercise_session_ratio_scope() -> None:
    cfg = Settings(fee_user="fee.wallet.worker", fee_ratio=0.5, fee_ratio_scope="session")
    proxy = MinerProxy(cfg, MinerMetrics())
    controller = FeeController(cfg.fee_ratio)

    session_tracker = RatioTracker()
    first = await proxy._select_path(controller, session_tracker)
    assert first == "fee"

    await proxy._record_accepted("fee", 10.0, session_tracker)
    second = await proxy._select_path(controller, RatioTracker())
    assert second == "fee"


def test_proxy_uses_global_ratio_scope_for_route_selection() -> None:
    asyncio.run(_exercise_global_ratio_scope())


def test_proxy_uses_session_ratio_scope_for_route_selection() -> None:
    asyncio.run(_exercise_session_ratio_scope())


def test_proxy_fee_startup_policy_switch() -> None:
    strict_proxy = MinerProxy(Settings(fee_user="fee.wallet.worker", fee_path_startup_policy="strict"), MinerMetrics())
    best_effort_proxy = MinerProxy(
        Settings(fee_user="fee.wallet.worker", fee_path_startup_policy="best_effort"),
        MinerMetrics(),
    )

    assert strict_proxy._should_fail_on_fee_startup_error() is True
    assert best_effort_proxy._should_fail_on_fee_startup_error() is False
