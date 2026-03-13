from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RatioTracker:
    accepted_main_count: int = 0
    accepted_fee_count: int = 0
    accepted_main_work: float = 0.0
    accepted_fee_work: float = 0.0

    def ratio(self) -> float:
        total = self.accepted_main_work + self.accepted_fee_work
        if total <= 0:
            return 0.0
        return self.accepted_fee_work / total

    def record_accepted(self, route: str, difficulty: float) -> None:
        work = difficulty if difficulty > 0 else 1.0
        if route == "fee":
            self.accepted_fee_count += 1
            self.accepted_fee_work += work
            return
        self.accepted_main_count += 1
        self.accepted_main_work += work


class FeeController:
    def __init__(self, target_ratio: float) -> None:
        self.target_ratio = target_ratio

    def select_path(self, tracker: RatioTracker) -> str:
        if tracker.ratio() < self.target_ratio:
            return "fee"
        return "main"
