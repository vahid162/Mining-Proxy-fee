from app.fee import FeeController, RatioTracker, SelectionTracker


def test_fee_controller_selects_fee_when_routed_ratio_below_target() -> None:
    tracker = SelectionTracker(routed_main_work=95.0, routed_fee_work=4.0)
    controller = FeeController(0.05, max_consecutive_fee_jobs=5)
    assert controller.select_path(tracker) == "fee"


def test_fee_controller_selects_main_when_routed_ratio_reached() -> None:
    tracker = SelectionTracker(routed_main_work=95.0, routed_fee_work=5.0)
    controller = FeeController(0.05, max_consecutive_fee_jobs=5)
    assert controller.select_path(tracker) == "main"


def test_fee_controller_forces_main_after_max_consecutive_fee_jobs() -> None:
    tracker = SelectionTracker(consecutive_fee_jobs=3)
    controller = FeeController(0.5, max_consecutive_fee_jobs=3)
    assert controller.select_path(tracker) == "main"


def test_selection_tracker_records_routed_work_and_resets_streak_on_main() -> None:
    tracker = SelectionTracker()
    tracker.record_route("fee", 8.0)
    tracker.record_route("fee", 2.0)
    assert tracker.ratio() == 1.0
    assert tracker.consecutive_fee_jobs == 2

    tracker.record_route("main", 5.0)
    assert round(tracker.ratio(), 6) == round(10.0 / 15.0, 6)
    assert tracker.consecutive_fee_jobs == 0


def test_ratio_tracker_records_accepted_work_only_for_reporting() -> None:
    tracker = RatioTracker()
    tracker.record_accepted("fee", 8.0)
    tracker.record_accepted("main", 2.0)
    assert tracker.accepted_fee_count == 1
    assert tracker.accepted_main_count == 1
    assert tracker.ratio() == 0.8
