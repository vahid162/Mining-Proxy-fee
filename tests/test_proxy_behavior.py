import asyncio

from app.config import Settings
from app.fee import FeeController, RatioTracker, SelectionTracker
from app.proxy import MinerMetrics, MinerProxy


async def _exercise_global_ratio_scope() -> None:
    cfg = Settings(fee_user="fee.wallet.worker", fee_ratio=0.5, fee_ratio_scope="global", max_consecutive_fee_jobs=3)
    proxy = MinerProxy(cfg, MinerMetrics())
    controller = FeeController(cfg.fee_ratio, cfg.max_consecutive_fee_jobs)

    first = await proxy._select_path(controller, SelectionTracker())
    assert first == "fee"

    await proxy._record_route("fee", 10.0, SelectionTracker())
    second = await proxy._select_path(controller, SelectionTracker())
    assert second == "main"


async def _exercise_session_ratio_scope() -> None:
    cfg = Settings(fee_user="fee.wallet.worker", fee_ratio=0.5, fee_ratio_scope="session", max_consecutive_fee_jobs=3)
    proxy = MinerProxy(cfg, MinerMetrics())
    controller = FeeController(cfg.fee_ratio, cfg.max_consecutive_fee_jobs)

    session_selection_tracker = SelectionTracker()
    first = await proxy._select_path(controller, session_selection_tracker)
    assert first == "fee"

    await proxy._record_route("fee", 10.0, session_selection_tracker)
    second = await proxy._select_path(controller, SelectionTracker())
    assert second == "fee"


async def _exercise_repeated_fee_rejects_do_not_lock_with_guard() -> None:
    cfg = Settings(fee_user="fee.wallet.worker", fee_ratio=0.9, fee_ratio_scope="session", max_consecutive_fee_jobs=3)
    proxy = MinerProxy(cfg, MinerMetrics())
    controller = FeeController(cfg.fee_ratio, cfg.max_consecutive_fee_jobs)
    selection_tracker = SelectionTracker()
    accepted_tracker = RatioTracker()

    routes: list[str] = []
    for _ in range(10):
        route = await proxy._select_path(controller, selection_tracker)
        routes.append(route)
        await proxy._record_route(route, 1.0, selection_tracker)
        # Simulate reject flow: do not call _record_accepted

    assert "main" in routes
    assert accepted_tracker.accepted_fee_work == 0.0
    assert accepted_tracker.accepted_main_work == 0.0


async def _exercise_fallback_route_selection_not_stuck() -> None:
    cfg = Settings(fee_user="fee.wallet.worker", fee_ratio=0.8, fee_ratio_scope="session", max_consecutive_fee_jobs=2)
    proxy = MinerProxy(cfg, MinerMetrics())
    controller = FeeController(cfg.fee_ratio, cfg.max_consecutive_fee_jobs)
    selection_tracker = SelectionTracker()

    fallback_routes: list[str] = []
    for _ in range(8):
        route = await proxy._select_path(controller, selection_tracker)
        fallback_routes.append(route)
        await proxy._record_route(route, 1.0, selection_tracker)

    assert fallback_routes.count("main") >= 1


def test_proxy_uses_global_ratio_scope_for_route_selection() -> None:
    asyncio.run(_exercise_global_ratio_scope())


def test_proxy_uses_session_ratio_scope_for_route_selection() -> None:
    asyncio.run(_exercise_session_ratio_scope())


def test_proxy_repeated_fee_rejects_do_not_lock_with_guard() -> None:
    asyncio.run(_exercise_repeated_fee_rejects_do_not_lock_with_guard())


def test_proxy_fallback_route_selection_not_stuck_on_fee() -> None:
    asyncio.run(_exercise_fallback_route_selection_not_stuck())


def test_proxy_fee_startup_policy_switch() -> None:
    strict_proxy = MinerProxy(Settings(fee_user="fee.wallet.worker", fee_path_startup_policy="strict"), MinerMetrics())
    best_effort_proxy = MinerProxy(
        Settings(fee_user="fee.wallet.worker", fee_path_startup_policy="best_effort"),
        MinerMetrics(),
    )

    assert strict_proxy._should_fail_on_fee_startup_error() is True
    assert best_effort_proxy._should_fail_on_fee_startup_error() is False
