from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class StratumMessage:
    raw: dict[str, Any]

    @property
    def method(self) -> str | None:
        value = self.raw.get("method")
        return value if isinstance(value, str) else None

    @property
    def msg_id(self) -> int | str | None:
        return self.raw.get("id")

    @property
    def params(self) -> list[Any]:
        params = self.raw.get("params", [])
        if isinstance(params, list):
            return params
        return []

    def dumps(self) -> bytes:
        return (json.dumps(self.raw, separators=(",", ":")) + "\n").encode()


def parse_line(line: bytes) -> StratumMessage:
    payload = json.loads(line.decode().strip())
    if not isinstance(payload, dict):
        raise ValueError("Stratum payload must be an object")
    return StratumMessage(payload)


def extract_job_id(message: StratumMessage) -> str | None:
    if message.method != "mining.notify" or len(message.params) < 1:
        return None
    job_id = message.params[0]
    return str(job_id) if job_id is not None else None


def extract_submit_job_id(message: StratumMessage) -> str | None:
    if message.method != "mining.submit" or len(message.params) < 2:
        return None
    return str(message.params[1])
