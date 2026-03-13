from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RatioTracker:
    main_accepted: int = 0
    fee_accepted: int = 0

    def ratio(self) -> float:
        total = self.main_accepted + self.fee_accepted
        if total == 0:
            return 0.0
        return self.fee_accepted / total


class FeeController:
    def __init__(self, target_ratio: float) -> None:
        self.target_ratio = target_ratio

    def select_path(self, tracker: RatioTracker) -> str:
        if tracker.ratio() < self.target_ratio:
            return "fee"
        return "main"
