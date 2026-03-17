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


@dataclass
class SelectionTracker:
    routed_main_work: float = 0.0
    routed_fee_work: float = 0.0
    consecutive_fee_jobs: int = 0

    def ratio(self) -> float:
        total = self.routed_main_work + self.routed_fee_work
        if total <= 0:
            return 0.0
        return self.routed_fee_work / total

    def record_route(self, route: str, difficulty: float) -> None:
        work = difficulty if difficulty > 0 else 1.0
        if route == "fee":
            self.routed_fee_work += work
            self.consecutive_fee_jobs += 1
            return
        self.routed_main_work += work
        self.consecutive_fee_jobs = 0


class FeeController:
    def __init__(self, target_ratio: float, max_consecutive_fee_jobs: int = 5) -> None:
        self.target_ratio = target_ratio
        self.max_consecutive_fee_jobs = max_consecutive_fee_jobs

    def select_path(self, tracker: SelectionTracker) -> str:
        if tracker.consecutive_fee_jobs >= self.max_consecutive_fee_jobs:
            return "main"
        if tracker.ratio() < self.target_ratio:
            return "fee"
        return "main"
