from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from .config import Settings
from .fee import FeeController, RatioTracker
from .stratum import (
    StratumMessage,
    extract_job_id,
    extract_set_difficulty,
    extract_submit_job_id,
    parse_line,
)

logger = logging.getLogger(__name__)
RPC_TIMEOUT_SECONDS = 15


async def open_socks5_connection(
    socks_host: str,
    socks_port: int,
    dst_host: str,
    dst_port: int,
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    reader, writer = await asyncio.open_connection(socks_host, socks_port)
    writer.write(b"\x05\x01\x00")
    await writer.drain()
    resp = await reader.readexactly(2)
    if resp != b"\x05\x00":
        raise RuntimeError("SOCKS5 method negotiation failed")

    host_bytes = dst_host.encode()
    req = b"\x05\x01\x00\x03" + bytes([len(host_bytes)]) + host_bytes + dst_port.to_bytes(2, "big")
    writer.write(req)
    await writer.drain()

    head = await reader.readexactly(4)
    if head[1] != 0x00:
        raise RuntimeError(f"SOCKS5 connect failed with code {head[1]}")

    atyp = head[3]
    if atyp == 1:
        await reader.readexactly(6)
    elif atyp == 3:
        length = (await reader.readexactly(1))[0]
        await reader.readexactly(length + 2)
    elif atyp == 4:
        await reader.readexactly(18)
    else:
        raise RuntimeError("SOCKS5 returned unknown address type")
    return reader, writer


@dataclass
class MinerMetrics:
    active_miners: int = 0
    submitted_main: int = 0
    submitted_fee: int = 0
    accepted_main: int = 0
    accepted_fee: int = 0
    rejected_main: int = 0
    rejected_fee: int = 0
    accepted_main_work: float = 0.0
    accepted_fee_work: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def snapshot(self) -> dict[str, float | int]:
        async with self.lock:
            total_work = self.accepted_fee_work + self.accepted_main_work
            ratio = (self.accepted_fee_work / total_work) if total_work else 0.0
            return {
                "active_miners": self.active_miners,
                "submitted_main": self.submitted_main,
                "submitted_fee": self.submitted_fee,
                "accepted_main": self.accepted_main,
                "accepted_fee": self.accepted_fee,
                "rejected_main": self.rejected_main,
                "rejected_fee": self.rejected_fee,
                "accepted_main_work": round(self.accepted_main_work, 6),
                "accepted_fee_work": round(self.accepted_fee_work, 6),
                "fee_ratio": round(ratio, 6),
            }


@dataclass
class PathSessionState:
    label: str
    current_difficulty: float = 1.0
    jobs: dict[str, float] = field(default_factory=dict)


@dataclass
class MinerSessionState:
    miner_user: str | None = None
    miner_password: str = "x"
    active_label: str = "main"
    job_route: dict[str, str] = field(default_factory=dict)
    paths: dict[str, PathSessionState] = field(
        default_factory=lambda: {
            "main": PathSessionState("main"),
            "fee": PathSessionState("fee"),
        }
    )


class UpstreamSession:
    def __init__(self, cfg: Settings, label: str) -> None:
        self.cfg = cfg
        self.label = label
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.pending: dict[Any, asyncio.Future[StratumMessage]] = {}

    async def connect(self) -> None:
        last_exc: Exception | None = None
        for port in (self.cfg.upstream_primary_port, self.cfg.upstream_secondary_port):
            try:
                self.reader, self.writer = await open_socks5_connection(
                    self.cfg.socks5_host,
                    self.cfg.socks5_port,
                    self.cfg.upstream_host,
                    port,
                )
                logger.info("upstream_%s_connected port=%s", self.label, port)
                return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("upstream_%s_connect_failed port=%s err=%s", self.label, port, exc)
        raise RuntimeError(f"unable to connect upstream {self.label}") from last_exc

    async def send(self, message: dict[str, Any]) -> None:
        if not self.writer:
            raise RuntimeError("upstream writer is not available")
        self.writer.write(StratumMessage(message).dumps())
        await self.writer.drain()

    async def close(self) -> None:
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()


class MinerProxy:
    def __init__(self, cfg: Settings, metrics: MinerMetrics) -> None:
        self.cfg = cfg
        self.metrics = metrics

    async def handle(self, miner_reader: asyncio.StreamReader, miner_writer: asyncio.StreamWriter) -> None:
        controller = FeeController(self.cfg.fee_ratio)
        tracker = RatioTracker()
        session = MinerSessionState(miner_password=self.cfg.main_password)
        main: UpstreamSession | None = None
        fee: UpstreamSession | None = None
        try:
            async with self.metrics.lock:
                self.metrics.active_miners += 1

            main = UpstreamSession(self.cfg, "main")
            fee = UpstreamSession(self.cfg, "fee")
            await main.connect()
            await fee.connect()

            t_main = asyncio.create_task(self._relay_upstream(main, miner_writer, session, controller, tracker))
            t_fee = asyncio.create_task(self._relay_upstream(fee, miner_writer, session, controller, tracker))
            t_miner = asyncio.create_task(self._relay_miner(miner_reader, miner_writer, main, fee, controller, tracker, session))

            done, pending = await asyncio.wait({t_main, t_fee, t_miner}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                err = task.exception()
                if err:
                    raise err
        except Exception as exc:  # noqa: BLE001
            logger.warning("miner_session_ended err=%s", exc)
        finally:
            if main:
                await main.close()
            if fee:
                await fee.close()
            miner_writer.close()
            await miner_writer.wait_closed()
            async with self.metrics.lock:
                self.metrics.active_miners -= 1

    async def _relay_upstream(
        self,
        upstream: UpstreamSession,
        miner_writer: asyncio.StreamWriter,
        session: MinerSessionState,
        controller: FeeController,
        tracker: RatioTracker,
    ) -> None:
        assert upstream.reader is not None
        path_state = session.paths[upstream.label]
        while True:
            line = await upstream.reader.readline()
            if not line:
                return

            try:
                message = parse_line(line)
            except Exception:  # noqa: BLE001
                logger.warning("invalid_stratum_message label=%s", upstream.label)
                continue

            diff = extract_set_difficulty(message)
            if diff is not None:
                path_state.current_difficulty = diff

            if message.method == "mining.notify":
                target = controller.select_path(tracker)
                if upstream.label != target:
                    continue
                session.active_label = upstream.label
                job_id = extract_job_id(message)
                if job_id:
                    path_state.jobs[job_id] = path_state.current_difficulty
                    session.job_route[job_id] = upstream.label
                miner_writer.write(line)
                await miner_writer.drain()
                continue

            if message.method in ("mining.set_difficulty", "mining.set_extranonce"):
                if upstream.label == session.active_label:
                    miner_writer.write(line)
                    await miner_writer.drain()
                continue

            if message.msg_id in upstream.pending:
                fut = upstream.pending.pop(message.msg_id)
                if not fut.done():
                    fut.set_result(message)

    async def _rpc(self, upstream: UpstreamSession, payload: dict[str, Any]) -> StratumMessage:
        loop = asyncio.get_running_loop()
        request_id = payload.get("id")
        fut: asyncio.Future[StratumMessage] = loop.create_future()
        upstream.pending[request_id] = fut
        await upstream.send(payload)
        return await asyncio.wait_for(fut, timeout=RPC_TIMEOUT_SECONDS)

    async def _relay_miner(
        self,
        miner_reader: asyncio.StreamReader,
        miner_writer: asyncio.StreamWriter,
        main: UpstreamSession,
        fee: UpstreamSession,
        controller: FeeController,
        tracker: RatioTracker,
        session: MinerSessionState,
    ) -> None:
        while True:
            line = await miner_reader.readline()
            if not line:
                return
            msg = parse_line(line)
            method = msg.method

            if method == "mining.subscribe":
                main_resp = await self._rpc(main, msg.raw)
                fee_resp = await self._rpc(fee, msg.raw)
                if fee_resp.raw.get("error"):
                    logger.warning("fee_subscribe_error=%s", fee_resp.raw.get("error"))
                miner_writer.write(main_resp.dumps())
                await miner_writer.drain()
                continue

            if method == "mining.authorize":
                if len(msg.params) >= 1 and isinstance(msg.params[0], str):
                    session.miner_user = msg.params[0]
                if len(msg.params) >= 2 and isinstance(msg.params[1], str):
                    session.miner_password = msg.params[1]

                if not session.miner_user:
                    raise RuntimeError("miner username is required before authorize")

                main_authorize = {
                    "id": msg.msg_id,
                    "method": "mining.authorize",
                    "params": [session.miner_user, session.miner_password],
                }
                fee_authorize = {
                    "id": msg.msg_id,
                    "method": "mining.authorize",
                    "params": [self.cfg.fee_user, self.cfg.fee_password],
                }
                main_resp = await self._rpc(main, main_authorize)
                fee_resp = await self._rpc(fee, fee_authorize)
                if fee_resp.raw.get("error"):
                    logger.warning("fee_authorize_error=%s", fee_resp.raw.get("error"))
                miner_writer.write(main_resp.dumps())
                await miner_writer.drain()
                continue

            if method == "mining.submit":
                if not session.miner_user and msg.params and isinstance(msg.params[0], str):
                    session.miner_user = msg.params[0]

                job_id = extract_submit_job_id(msg)
                route = session.job_route.get(job_id or "", controller.select_path(tracker))
                session.active_label = route
                route_state = session.paths[route]
                difficulty = route_state.jobs.get(job_id or "", route_state.current_difficulty)

                params = list(msg.params)
                if route == "fee":
                    if not params:
                        params = [self.cfg.fee_user]
                    else:
                        params[0] = self.cfg.fee_user
                    req = {"id": msg.msg_id, "method": "mining.submit", "params": params}
                    resp = await self._rpc(fee, req)
                    async with self.metrics.lock:
                        self.metrics.submitted_fee += 1
                        if resp.raw.get("result") is True:
                            tracker.record_accepted("fee", difficulty)
                            self.metrics.accepted_fee += 1
                            self.metrics.accepted_fee_work += difficulty
                        else:
                            self.metrics.rejected_fee += 1
                else:
                    if params and session.miner_user:
                        params[0] = session.miner_user
                    req = {"id": msg.msg_id, "method": "mining.submit", "params": params}
                    resp = await self._rpc(main, req)
                    async with self.metrics.lock:
                        self.metrics.submitted_main += 1
                        if resp.raw.get("result") is True:
                            tracker.record_accepted("main", difficulty)
                            self.metrics.accepted_main += 1
                            self.metrics.accepted_main_work += difficulty
                        else:
                            self.metrics.rejected_main += 1

                miner_writer.write(resp.dumps())
                await miner_writer.drain()
                continue

            resp = await self._rpc(main, msg.raw)
            miner_writer.write(resp.dumps())
            await miner_writer.drain()
