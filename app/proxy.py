from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from itertools import count
from typing import Any

from .config import Settings
from .fee import FeeController, RatioTracker, SelectionTracker
from .stratum import StratumMessage, extract_job_id, extract_set_difficulty, extract_submit_job_id, parse_line

logger = logging.getLogger(__name__)
SESSION_COUNTER = count(1)


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
    upstream_reconnects_main: int = 0
    upstream_reconnects_fee: int = 0
    upstream_failovers_main: int = 0
    upstream_failovers_fee: int = 0
    auth_failures_main: int = 0
    auth_failures_fee: int = 0
    job_mismatch_count: int = 0
    dropped_sessions_max_limit: int = 0
    local_submit_rejects: int = 0
    fee_not_ready_skips: int = 0
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
                "upstream_reconnects_main": self.upstream_reconnects_main,
                "upstream_reconnects_fee": self.upstream_reconnects_fee,
                "upstream_failovers_main": self.upstream_failovers_main,
                "upstream_failovers_fee": self.upstream_failovers_fee,
                "auth_failures_main": self.auth_failures_main,
                "auth_failures_fee": self.auth_failures_fee,
                "job_mismatch_count": self.job_mismatch_count,
                "dropped_sessions_max_limit": self.dropped_sessions_max_limit,
                "local_submit_rejects": self.local_submit_rejects,
                "fee_not_ready_skips": self.fee_not_ready_skips,
            }


@dataclass
class MinerSessionState:
    session_id: str
    client_addr: str
    miner_user: str | None = None
    miner_password: str = "x"
    active_label: str = "main"
    job_generation: int = 0
    job_route: dict[str, str] = field(default_factory=dict)
    job_records: dict[str, "DownstreamJobRecord"] = field(default_factory=dict)
    job_difficulty: dict[str, float] = field(default_factory=dict)
    current_difficulty: float = 1.0
    awaiting_post_difficulty_job: bool = False
    awaiting_post_extranonce_job: bool = False
    last_invalidation_cause: str = "-"
    subscribe_raw: dict[str, Any] | None = None
    subscribe_result: Any = None
    subscribe_error: Any = None
    main_authorized: bool = False
    fee_authorized: bool = False
    fee_ready: bool = False


@dataclass
class DownstreamJobRecord:
    route: str
    upstream_job_id: str
    generation: int
    clean_jobs: bool


class UpstreamSession:
    def __init__(self, cfg: Settings) -> None:
        self.cfg = cfg
        self.label = "main"
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.pending: dict[Any, asyncio.Future[StratumMessage]] = {}
        self.pending_slots = asyncio.Semaphore(cfg.max_pending_rpcs)
        self._host = self.cfg.upstream_host
        self._ports = [self.cfg.upstream_primary_port, self.cfg.upstream_secondary_port]
        self._active_port_index = 0
        self.connected_port: int | None = None

    async def connect(self, start_index: int = 0) -> None:
        last_exc: Exception | None = None
        for offset in range(len(self._ports)):
            index = (start_index + offset) % len(self._ports)
            port = self._ports[index]
            try:
                self.reader, self.writer = await open_socks5_connection(
                    self.cfg.socks5_host,
                    self.cfg.socks5_port,
                    self._host,
                    port,
                )
                self._active_port_index = index
                self.connected_port = port
                logger.info("upstream_%s_connected port=%s", self.label, port)
                return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("upstream_%s_connect_failed port=%s err=%s", self.label, port, exc)
        raise RuntimeError(f"unable to connect upstream {self.label}") from last_exc

    async def reconnect_with_backoff(self) -> bool:
        await self.close()
        backoff = self.cfg.reconnect_initial_backoff_seconds
        attempts = 0
        next_index = (self._active_port_index + 1) % len(self._ports)

        while True:
            try:
                await self.connect(start_index=next_index)
                return True
            except Exception as exc:  # noqa: BLE001
                attempts += 1
                logger.warning(
                    "upstream_%s_reconnect_failed attempt=%s err=%s backoff=%.2f",
                    self.label,
                    attempts,
                    exc,
                    backoff,
                )
                if self.cfg.reconnect_attempts and attempts >= self.cfg.reconnect_attempts:
                    return False
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self.cfg.reconnect_max_backoff_seconds)

    async def send(self, message: dict[str, Any]) -> None:
        if not self.writer:
            raise RuntimeError("upstream writer is not available")
        self.writer.write(StratumMessage(message).dumps())
        await asyncio.wait_for(self.writer.drain(), timeout=self.cfg.write_timeout_seconds)

    async def close(self) -> None:
        for fut in self.pending.values():
            if not fut.done():
                fut.cancel()
        self.pending.clear()

        if self.writer:
            self.writer.close()
            try:
                await asyncio.wait_for(self.writer.wait_closed(), timeout=2.0)
            except (TimeoutError, asyncio.TimeoutError):
                pass
            self.writer = None
            self.reader = None


class MinerProxy:
    def __init__(self, cfg: Settings, metrics: MinerMetrics) -> None:
        self.cfg = cfg
        self.metrics = metrics
        self._session_slots = asyncio.Semaphore(cfg.max_sessions)
        self._global_selection_tracker = SelectionTracker()
        self._global_controller = FeeController(cfg.fee_ratio, cfg.max_consecutive_fee_jobs)
        self._global_tracker_lock = asyncio.Lock()


    async def _select_path(self, controller: FeeController, session_tracker: SelectionTracker) -> str:
        if self.cfg.fee_ratio_scope == "session":
            return controller.select_path(session_tracker)

        async with self._global_tracker_lock:
            return self._global_controller.select_path(self._global_selection_tracker)

    async def _record_route(self, route: str, difficulty: float, session_tracker: SelectionTracker) -> None:
        session_tracker.record_route(route, difficulty)
        if self.cfg.fee_ratio_scope == "global":
            async with self._global_tracker_lock:
                self._global_selection_tracker.record_route(route, difficulty)

    async def _record_accepted(self, route: str, difficulty: float, session_tracker: RatioTracker) -> None:
        session_tracker.record_accepted(route, difficulty)

    def _extract_notify_clean_jobs(self, message: StratumMessage) -> bool:
        if message.method != "mining.notify" or not message.params:
            return False
        last = message.params[-1]
        return isinstance(last, bool) and last

    def _bump_job_generation(self, session: MinerSessionState, reason: str) -> None:
        session.job_generation += 1
        session.last_invalidation_cause = reason
        self._log_session(session, "job_generation_bumped", generation=session.job_generation, reason=reason)

    def _invalidate_downstream_jobs(self, session: MinerSessionState, reason: str) -> None:
        self._bump_job_generation(session, reason)
        session.awaiting_post_difficulty_job = False
        session.awaiting_post_extranonce_job = False
        self._disarm_fee_route(session, reason)

    def _is_fee_ready_boundary_satisfied(self, session: MinerSessionState) -> bool:
        return bool(
            session.fee_authorized
            and not session.awaiting_post_difficulty_job
            and not session.awaiting_post_extranonce_job
        )

    def _disarm_fee_route(self, session: MinerSessionState, reason: str) -> None:
        session.fee_ready = False
        self._log_session(session, "fee_route_disarmed", reason=reason)

    def _arm_fee_route(self, session: MinerSessionState, reason: str, job_id: str | None = None) -> None:
        session.fee_ready = True
        self._log_session(session, "fee_route_armed", reason=reason, job_id=job_id or "-")

    def _should_fail_on_fee_startup_error(self) -> bool:
        return self.cfg.fee_path_startup_policy == "strict"

    def _log_session(self, session: MinerSessionState, event: str, **fields: Any) -> None:
        pairs = " ".join(f"{key}={value}" for key, value in fields.items())
        logger.info(
            "event=%s session_id=%s client=%s user=%s %s",
            event,
            session.session_id,
            session.client_addr,
            session.miner_user or "-",
            pairs,
        )

    async def handle(self, miner_reader: asyncio.StreamReader, miner_writer: asyncio.StreamWriter) -> None:
        session_id = f"s{next(SESSION_COUNTER):08d}"
        peername = miner_writer.get_extra_info("peername")
        client_addr = str(peername) if peername else "unknown"

        try:
            await asyncio.wait_for(self._session_slots.acquire(), timeout=0.01)
        except asyncio.TimeoutError:
            logger.warning("max_sessions_reached session_id=%s client=%s limit=%s", session_id, client_addr, self.cfg.max_sessions)
            async with self.metrics.lock:
                self.metrics.dropped_sessions_max_limit += 1
            miner_writer.close()
            await miner_writer.wait_closed()
            return

        controller = FeeController(self.cfg.fee_ratio, self.cfg.max_consecutive_fee_jobs)
        accepted_tracker = RatioTracker()
        selection_tracker = SelectionTracker()
        session = MinerSessionState(session_id=session_id, client_addr=client_addr, miner_password=self.cfg.main_password)
        upstream: UpstreamSession | None = None
        tasks: list[asyncio.Task[Any]] = []

        try:
            async with self.metrics.lock:
                self.metrics.active_miners += 1

            self._disarm_fee_route(session, "session_start")
            self._log_session(session, "session_start")
            self._disarm_fee_route(session, "session_start")
            upstream = UpstreamSession(self.cfg)
            await upstream.connect()
            self._log_session(session, "upstream_connected", port=upstream.connected_port)

            tasks = [
                asyncio.create_task(self._relay_upstream(upstream, miner_writer, session, controller, selection_tracker)),
                asyncio.create_task(self._relay_miner(miner_reader, miner_writer, upstream, controller, selection_tracker, accepted_tracker, session)),
            ]

            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                err = task.exception()
                if err:
                    raise err
        except Exception as exc:  # noqa: BLE001
            self._log_session(session, "session_error", err=exc)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if upstream:
                await upstream.close()
            miner_writer.close()
            try:
                await asyncio.wait_for(miner_writer.wait_closed(), timeout=2.0)
            except (TimeoutError, asyncio.TimeoutError):
                pass
            async with self.metrics.lock:
                self.metrics.active_miners -= 1
            self._log_session(session, "session_end")
            self._session_slots.release()

    async def _safe_miner_write(self, miner_writer: asyncio.StreamWriter, payload: bytes) -> None:
        miner_writer.write(payload)
        await asyncio.wait_for(miner_writer.drain(), timeout=self.cfg.write_timeout_seconds)

    async def _resync_after_reconnect(self, upstream: UpstreamSession, session: MinerSessionState) -> None:
        if session.subscribe_raw is not None:
            subscribe_payload = dict(session.subscribe_raw)
            await self._rpc(upstream, subscribe_payload)

        if session.miner_user:
            main_auth_payload = {
                "id": 10_000_001,
                "method": "mining.authorize",
                "params": [session.miner_user, session.miner_password],
            }
            fee_auth_payload = {
                "id": 10_000_002,
                "method": "mining.authorize",
                "params": [self.cfg.fee_user, self.cfg.fee_password],
            }
            await self._rpc(upstream, main_auth_payload)
            await self._rpc(upstream, fee_auth_payload)

    async def _relay_upstream(
        self,
        upstream: UpstreamSession,
        miner_writer: asyncio.StreamWriter,
        session: MinerSessionState,
        controller: FeeController,
        tracker: SelectionTracker,
    ) -> None:
        while True:
            if upstream.reader is None:
                if not await upstream.reconnect_with_backoff():
                    raise RuntimeError("upstream_permanently_down")
                self._invalidate_downstream_jobs(session, "stale_due_to_reconnect")
                await self._resync_after_reconnect(upstream, session)

                async with self.metrics.lock:
                    self.metrics.upstream_reconnects_main += 1
                    self.metrics.upstream_reconnects_fee += 1
                self._log_session(session, "upstream_reconnected", port=upstream.connected_port)

            assert upstream.reader is not None
            try:
                line = await asyncio.wait_for(
                    upstream.reader.readline(),
                    timeout=self.cfg.upstream_read_timeout_seconds,
                )
                if not line:
                    raise ConnectionError("upstream closed connection")
            except (ConnectionError, asyncio.TimeoutError, TimeoutError) as exc:
                old_port = upstream.connected_port
                self._log_session(session, "upstream_read_error", err=exc, old_port=old_port)
                if not await upstream.reconnect_with_backoff():
                    raise RuntimeError("upstream_permanently_down") from exc
                self._invalidate_downstream_jobs(session, "stale_due_to_reconnect")
                await self._resync_after_reconnect(upstream, session)
                async with self.metrics.lock:
                    self.metrics.upstream_reconnects_main += 1
                    self.metrics.upstream_reconnects_fee += 1
                    if old_port != upstream.connected_port:
                        self.metrics.upstream_failovers_main += 1
                        self.metrics.upstream_failovers_fee += 1
                self._log_session(
                    session,
                    "upstream_failover",
                    old_port=old_port,
                    new_port=upstream.connected_port,
                )
                continue

            try:
                message = parse_line(line)
            except Exception:  # noqa: BLE001
                self._log_session(session, "invalid_upstream_message")
                continue

            diff = extract_set_difficulty(message)
            if diff is not None:
                session.current_difficulty = diff
                if not session.awaiting_post_difficulty_job:
                    session.awaiting_post_difficulty_job = True
                    self._disarm_fee_route(session, "stale_due_to_difficulty_epoch")
                    self._log_session(
                        session,
                        "difficulty_epoch_pending",
                        next_difficulty=round(diff, 6),
                    )

            if message.method == "mining.notify":
                job_id = extract_job_id(message)
                clean_jobs = self._extract_notify_clean_jobs(message)
                if clean_jobs:
                    self._bump_job_generation(session, "stale_due_to_clean_jobs")
                    self._disarm_fee_route(session, "stale_due_to_clean_jobs")

                if session.awaiting_post_difficulty_job:
                    self._bump_job_generation(session, "stale_due_to_difficulty_epoch")
                    session.awaiting_post_difficulty_job = False
                    self._log_session(
                        session,
                        "difficulty_epoch_committed",
                        generation=session.job_generation,
                        job_id=job_id or "-",
                    )

                if session.awaiting_post_extranonce_job:
                    self._bump_job_generation(session, "stale_due_to_extranonce_reset")
                    session.awaiting_post_extranonce_job = False
                    self._log_session(
                        session,
                        "extranonce_reset_committed",
                        generation=session.job_generation,
                        job_id=job_id or "-",
                    )

                target = await self._select_path(controller, tracker)
                if target == "fee" and not session.fee_ready:
                    async with self.metrics.lock:
                        self.metrics.fee_not_ready_skips += 1
                    self._log_session(session, "fee_route_not_ready_skip", job_id=job_id or "-")
                    self._log_session(session, "fee_job_suppressed_until_ready", job_id=job_id or "-")
                    if self._is_fee_ready_boundary_satisfied(session):
                        self._arm_fee_route(session, "fresh_fee_notify_after_boundary", job_id=job_id)
                    target = "main"
                session.active_label = target
                difficulty = session.current_difficulty
                await self._record_route(target, difficulty, tracker)
                if job_id:
                    session.job_difficulty[job_id] = difficulty
                    session.job_route[job_id] = target
                    session.job_records[job_id] = DownstreamJobRecord(
                        route=target,
                        upstream_job_id=job_id,
                        generation=session.job_generation,
                        clean_jobs=clean_jobs,
                    )
                await self._safe_miner_write(miner_writer, line)
                self._log_session(session, "notify_forwarded", path=target, job_id=job_id or "-")
                if self._can_arm_fee_route(session):
                    self._arm_fee_route(session, job_id)
                continue

            if message.method == "mining.set_extranonce":
                if not session.awaiting_post_extranonce_job:
                    session.awaiting_post_extranonce_job = True
                    self._disarm_fee_route(session, "stale_due_to_extranonce_reset")
                    self._log_session(session, "extranonce_reset_pending")
                await self._safe_miner_write(miner_writer, line)
                continue

            if message.method == "mining.set_difficulty":
                await self._safe_miner_write(miner_writer, line)
                continue

            if message.msg_id in upstream.pending:
                fut = upstream.pending.pop(message.msg_id)
                if not fut.done():
                    fut.set_result(message)
    async def _rpc(self, upstream: UpstreamSession, payload: dict[str, Any]) -> StratumMessage:
        request_id = payload.get("id")
        if request_id is None:
            raise RuntimeError("rpc payload requires id")

        await asyncio.wait_for(upstream.pending_slots.acquire(), timeout=self.cfg.rpc_timeout_seconds)
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[StratumMessage] = loop.create_future()
        upstream.pending[request_id] = fut

        try:
            await upstream.send(payload)
            return await asyncio.wait_for(fut, timeout=self.cfg.rpc_timeout_seconds)
        finally:
            upstream.pending.pop(request_id, None)
            upstream.pending_slots.release()

    async def _relay_miner(
        self,
        miner_reader: asyncio.StreamReader,
        miner_writer: asyncio.StreamWriter,
        upstream: UpstreamSession,
        controller: FeeController,
        selection_tracker: SelectionTracker,
        accepted_tracker: RatioTracker,
        session: MinerSessionState,
    ) -> None:
        while True:
            line = await miner_reader.readline()
            if not line:
                return
            msg = parse_line(line)
            method = msg.method

            if method == "mining.subscribe":
                if session.subscribe_raw is None:
                    session.subscribe_raw = dict(msg.raw)
                    resp = await self._rpc(upstream, msg.raw)
                    session.subscribe_result = resp.raw.get("result")
                    session.subscribe_error = resp.raw.get("error")
                    await self._safe_miner_write(miner_writer, resp.dumps())
                    self._log_session(session, "subscribe_ok")
                else:
                    cached = {
                        "id": msg.msg_id,
                        "result": session.subscribe_result,
                        "error": session.subscribe_error,
                    }
                    await self._safe_miner_write(miner_writer, StratumMessage(cached).dumps())
                    self._log_session(session, "subscribe_cached")
                continue

            if method == "mining.authorize":
                if len(msg.params) >= 1 and isinstance(msg.params[0], str):
                    session.miner_user = msg.params[0]
                if len(msg.params) >= 2 and isinstance(msg.params[1], str):
                    session.miner_password = msg.params[1]

                if session.main_authorized or session.fee_authorized or session.job_records:
                    self._invalidate_downstream_jobs(session, "stale_due_to_reauthorize")

                if not session.miner_user:
                    raise RuntimeError("miner username is required before authorize")

                main_authorize = {
                    "id": msg.msg_id,
                    "method": "mining.authorize",
                    "params": [session.miner_user, session.miner_password],
                }
                fee_authorize = {
                    "id": f"fee-{msg.msg_id}",
                    "method": "mining.authorize",
                    "params": [self.cfg.fee_user, self.cfg.fee_password],
                }
                main_resp = await self._rpc(upstream, main_authorize)
                fee_resp = await self._rpc(upstream, fee_authorize)
                session.main_authorized = bool(main_resp.raw.get("result") is True)
                session.fee_authorized = bool(fee_resp.raw.get("result") is True)
                if not session.fee_authorized:
                    self._disarm_fee_route(session, "fee_authorize_failed")

                async with self.metrics.lock:
                    if not session.main_authorized:
                        self.metrics.auth_failures_main += 1
                    if not session.fee_authorized:
                        self.metrics.auth_failures_fee += 1

                self._log_session(session, "authorize_result", main_ok=session.main_authorized, fee_ok=session.fee_authorized)
                if fee_resp.raw.get("error"):
                    self._log_session(session, "fee_authorize_error", error=fee_resp.raw.get("error"))
                if not session.fee_authorized and self._should_fail_on_fee_startup_error():
                    raise RuntimeError("fee_authorize_failed")
                await self._safe_miner_write(miner_writer, main_resp.dumps())
                continue

            if method == "mining.submit":
                if not session.miner_user and msg.params and isinstance(msg.params[0], str):
                    session.miner_user = msg.params[0]

                job_id = extract_submit_job_id(msg)
                job_record = session.job_records.get(job_id or "") if job_id else None
                if not job_record:
                    async with self.metrics.lock:
                        self.metrics.job_mismatch_count += 1
                        self.metrics.local_submit_rejects += 1
                    self._log_session(session, "local_submit_rejected", reason="unknown_job", job_id=job_id or "-")
                    local_reject = {
                        "id": msg.msg_id,
                        "result": False,
                        "error": [21, "stale/unknown job: local reject", None],
                    }
                    await self._safe_miner_write(miner_writer, StratumMessage(local_reject).dumps())
                    continue

                if job_record.generation != session.job_generation:
                    async with self.metrics.lock:
                        self.metrics.job_mismatch_count += 1
                        self.metrics.local_submit_rejects += 1
                    self._log_session(
                        session,
                        "local_submit_rejected",
                        reason="generation_mismatch",
                        job_id=job_id or "-",
                        job_generation=job_record.generation,
                        active_generation=session.job_generation,
                        invalidation_cause=session.last_invalidation_cause,
                    )
                    local_reject = {
                        "id": msg.msg_id,
                        "result": False,
                        "error": [21, "stale/unknown job: local reject", None],
                    }
                    await self._safe_miner_write(miner_writer, StratumMessage(local_reject).dumps())
                    continue

                route = job_record.route

                session.active_label = route
                difficulty = session.job_difficulty.get(job_id or "", session.current_difficulty)

                params = list(msg.params)
                if route == "fee":
                    if not params:
                        params = [self.cfg.fee_user]
                    else:
                        params[0] = self.cfg.fee_user
                    req = {"id": msg.msg_id, "method": "mining.submit", "params": params}
                    resp = await self._rpc(upstream, req)
                    async with self.metrics.lock:
                        self.metrics.submitted_fee += 1
                        if resp.raw.get("result") is True:
                            await self._record_accepted("fee", difficulty, accepted_tracker)
                            self.metrics.accepted_fee += 1
                            self.metrics.accepted_fee_work += difficulty
                        else:
                            self.metrics.rejected_fee += 1
                else:
                    if params and session.miner_user:
                        params[0] = session.miner_user
                    req = {"id": msg.msg_id, "method": "mining.submit", "params": params}
                    resp = await self._rpc(upstream, req)
                    async with self.metrics.lock:
                        self.metrics.submitted_main += 1
                        if resp.raw.get("result") is True:
                            await self._record_accepted("main", difficulty, accepted_tracker)
                            self.metrics.accepted_main += 1
                            self.metrics.accepted_main_work += difficulty
                        else:
                            self.metrics.rejected_main += 1

                log_fields: dict[str, Any] = {
                    "route": route,
                    "job_id": job_id or "-",
                    "accepted": bool(resp.raw.get("result") is True),
                    "difficulty": round(difficulty, 6),
                }
                if resp.raw.get("result") is not True and resp.raw.get("error") is not None:
                    log_fields["error"] = resp.raw.get("error")
                self._log_session(session, "submit_result", **log_fields)
                await self._safe_miner_write(miner_writer, resp.dumps())
                continue

            resp = await self._rpc(upstream, msg.raw)
            self._log_session(session, "forward_main_method", method=method or "-")
            await self._safe_miner_write(miner_writer, resp.dumps())
