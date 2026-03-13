from app.fee import FeeController, RatioTracker


def test_fee_controller_selects_fee_when_weighted_ratio_below_target() -> None:
    tracker = RatioTracker(accepted_main_work=95.0, accepted_fee_work=4.0)
    controller = FeeController(0.05)
    assert controller.select_path(tracker) == "fee"


def test_fee_controller_selects_main_when_weighted_ratio_reached() -> None:
    tracker = RatioTracker(accepted_main_work=95.0, accepted_fee_work=5.0)
    controller = FeeController(0.05)
    assert controller.select_path(tracker) == "main"


def test_ratio_tracker_records_weighted_work() -> None:
    tracker = RatioTracker()
    tracker.record_accepted("fee", 8.0)
    tracker.record_accepted("main", 2.0)
    assert tracker.accepted_fee_count == 1
    assert tracker.accepted_main_count == 1
    assert tracker.ratio() == 0.8
