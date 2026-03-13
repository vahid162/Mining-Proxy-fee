from app.fee import FeeController, RatioTracker


def test_fee_controller_selects_fee_when_ratio_below_target() -> None:
    tracker = RatioTracker(main_accepted=95, fee_accepted=4)
    controller = FeeController(0.05)
    assert controller.select_path(tracker) == "fee"


def test_fee_controller_selects_main_when_ratio_reached() -> None:
    tracker = RatioTracker(main_accepted=95, fee_accepted=5)
    controller = FeeController(0.05)
    assert controller.select_path(tracker) == "main"
