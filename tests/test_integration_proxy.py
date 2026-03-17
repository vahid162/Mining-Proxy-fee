import asyncio
import json
import logging
from contextlib import suppress
from dataclasses import dataclass, field

from app.config import Settings
from app.proxy import MinerMetrics, MinerProxy, UpstreamSession


async def send_msg(writer: asyncio.StreamWriter, payload: dict) -> None:
    writer.write((json.dumps(payload) + "\n").encode())
    await writer.drain()


async def read_msg(reader: asyncio.StreamReader) -> dict:
    line = await asyncio.wait_for(reader.readline(), timeout=3.0)
    if not line:
        raise RuntimeError("connection closed")
    return json.loads(line.decode())


async def read_until_method(reader: asyncio.StreamReader, method: str, timeout: float = 3.0) -> dict:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        msg = await read_msg(reader)
        if msg.get("method") == method:
            return msg
    raise TimeoutError(f"method {method} not received")


@dataclass
class FakePool:
    authorize_main_success: bool = True
    authorize_fee_success: bool = True
    submit_success: bool = True
    submit_error: list | None = None
    close_on_submit: bool = False
    writers: list[asyncio.StreamWriter] = field(default_factory=list)
    authorizations: list[str] = field(default_factory=list)
    submits: list[tuple[str, str]] = field(default_factory=list)

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.writers.append(writer)
        try:
            while True:
                line = await reader.readline()
                if not line:
                    return
                msg = json.loads(line.decode())
                method = msg.get("method")
                mid = msg.get("id")

                if method == "mining.subscribe":
                    await send_msg(writer, {"id": mid, "result": [None, "aa", 4], "error": None})
                elif method == "mining.authorize":
                    user = msg.get("params", [""])[0]
                    self.authorizations.append(user)
                    is_fee = user == "fee.wallet.worker"
                    result = self.authorize_fee_success if is_fee else self.authorize_main_success
                    await send_msg(writer, {"id": mid, "result": result, "error": None})
                elif method == "mining.submit":
                    params = msg.get("params", [])
                    user = params[0] if len(params) >= 1 else ""
                    job_id = params[1] if len(params) >= 2 else ""
                    self.submits.append((user, job_id))
                    await send_msg(
                        writer,
                        {
                            "id": mid,
                            "result": self.submit_success,
                            "error": self.submit_error if not self.submit_success else None,
                        },
                    )
                    if self.close_on_submit:
                        writer.close()
                        await writer.wait_closed()
                        return
                else:
                    await send_msg(writer, {"id": mid, "result": True, "error": None})
        finally:
            with suppress(ValueError):
                self.writers.remove(writer)

    async def broadcast_difficulty(self, value: float) -> None:
        for writer in list(self.writers):
            await send_msg(writer, {"id": None, "method": "mining.set_difficulty", "params": [value]})

    async def broadcast_notify(self, job_id: str) -> None:
        for writer in list(self.writers):
            await send_msg(
                writer,
                {
                    "id": None,
                    "method": "mining.notify",
                    "params": [job_id, "", "", [], "", "", "", True],
                },
            )

    async def drop_all(self) -> None:
        for writer in list(self.writers):
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                return
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()


async def socks5_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        head = await reader.readexactly(2)
        n_methods = head[1]
        await reader.readexactly(n_methods)
        writer.write(b"\x05\x00")
        await writer.drain()

        req = await reader.readexactly(4)
        atyp = req[3]
        if atyp == 1:
            host = ".".join(str(x) for x in await reader.readexactly(4))
        elif atyp == 3:
            ln = (await reader.readexactly(1))[0]
            host = (await reader.readexactly(ln)).decode()
        else:
            raise RuntimeError("unsupported atyp")
        port = int.from_bytes(await reader.readexactly(2), "big")

        remote_reader, remote_writer = await asyncio.open_connection(host, port)
        writer.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        await writer.drain()

        t1 = asyncio.create_task(pipe(reader, remote_writer))
        t2 = asyncio.create_task(pipe(remote_reader, writer))
        await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
        t1.cancel()
        t2.cancel()
        await asyncio.gather(t1, t2, return_exceptions=True)
    finally:
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()


async def setup_system(
    *,
    authorize_fee_success: bool = True,
    submit_success: bool = True,
    submit_error: list | None = None,
) -> dict:
    pool = FakePool(authorize_fee_success=authorize_fee_success, submit_success=submit_success, submit_error=submit_error)
    pool_server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
    pool_port = pool_server.sockets[0].getsockname()[1]

    socks_server = await asyncio.start_server(socks5_handler, "127.0.0.1", 0)
    socks_port = socks_server.sockets[0].getsockname()[1]

    cfg = Settings(
        listen_host="127.0.0.1",
        listen_port=0,
        socks5_host="127.0.0.1",
        socks5_port=socks_port,
        upstream_host="127.0.0.1",
        upstream_primary_port=pool_port,
        upstream_secondary_port=pool_port,
        fee_user="fee.wallet.worker",
        fee_password="x",
        fee_ratio=0.5,
        rpc_timeout_seconds=2.0,
        upstream_read_timeout_seconds=0.3,
        write_timeout_seconds=2.0,
        reconnect_initial_backoff_seconds=0.05,
        reconnect_max_backoff_seconds=0.2,
        reconnect_attempts=10,
        max_pending_rpcs=64,
        fee_path_startup_policy="best_effort",
    )

    metrics = MinerMetrics()
    proxy = MinerProxy(cfg, metrics)
    proxy_server = await asyncio.start_server(proxy.handle, "127.0.0.1", 0)
    proxy_port = proxy_server.sockets[0].getsockname()[1]

    return {
        "pool": pool,
        "pool_server": pool_server,
        "socks_server": socks_server,
        "proxy_server": proxy_server,
        "proxy_port": proxy_port,
        "metrics": metrics,
        "pool_port": pool_port,
        "socks_port": socks_port,
    }


async def shutdown_system(system: dict) -> None:
    for key in ("proxy_server", "socks_server", "pool_server"):
        srv = system[key]
        srv.close()
        await srv.wait_closed()


async def integration_single_upstream_dual_authorize_and_routing() -> None:
    system = await setup_system()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", system["proxy_port"])

        await send_msg(writer, {"id": 1, "method": "mining.subscribe", "params": []})
        assert (await read_msg(reader))["id"] == 1

        await send_msg(writer, {"id": 2, "method": "mining.authorize", "params": ["main.wallet.worker1", "x"]})
        assert (await read_msg(reader))["result"] is True

        await system["pool"].broadcast_difficulty(4.0)
        await system["pool"].broadcast_notify("job-0")
        notify = await read_until_method(reader, "mining.notify")
        job_id_0 = notify["params"][0]

        await send_msg(writer, {"id": 3, "method": "mining.submit", "params": ["ignored", job_id_0, "aa", "bb", "cc"]})
        assert (await read_msg(reader))["result"] is True

        await system["pool"].broadcast_notify("job-1")
        notify2 = await read_until_method(reader, "mining.notify")
        job_id_1 = notify2["params"][0]
        await send_msg(writer, {"id": 4, "method": "mining.submit", "params": ["ignored", job_id_1, "aa", "bb", "cc"]})
        assert (await read_msg(reader))["result"] is True

        assert system["pool"].authorizations.count("main.wallet.worker1") == 1
        assert system["pool"].authorizations.count("fee.wallet.worker") == 1
        assert len(system["pool"].writers) == 1

        submit_users = [u for u, _ in system["pool"].submits]
        assert "main.wallet.worker1" in submit_users
        assert "fee.wallet.worker" in submit_users

        snapshot = await system["metrics"].snapshot()
        assert snapshot["submitted_main"] >= 1
        assert snapshot["submitted_fee"] >= 1
        assert snapshot["accepted_main"] >= 1
        assert snapshot["accepted_fee"] >= 1

        writer.close()
        await writer.wait_closed()
    finally:
        await shutdown_system(system)


async def integration_fee_auth_failure_metric_increment() -> None:
    system = await setup_system(authorize_fee_success=False)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", system["proxy_port"])
        await send_msg(writer, {"id": 1, "method": "mining.subscribe", "params": []})
        _ = await read_msg(reader)
        await send_msg(writer, {"id": 2, "method": "mining.authorize", "params": ["main.wallet.worker1", "x"]})
        assert (await read_msg(reader))["result"] is True

        snapshot = await system["metrics"].snapshot()
        assert snapshot["auth_failures_fee"] == 1

        writer.close()
        await writer.wait_closed()
    finally:
        await shutdown_system(system)


async def integration_reject_logging_includes_upstream_error() -> None:
    system = await setup_system(submit_success=False, submit_error=[20, "stale share", None])
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", system["proxy_port"])
        await send_msg(writer, {"id": 1, "method": "mining.subscribe", "params": []})
        _ = await read_msg(reader)
        await send_msg(writer, {"id": 2, "method": "mining.authorize", "params": ["main.wallet.worker1", "x"]})
        _ = await read_msg(reader)

        await system["pool"].broadcast_notify("job-reject")
        notify = await read_until_method(reader, "mining.notify")
        await send_msg(writer, {"id": 3, "method": "mining.submit", "params": ["main.wallet.worker1", notify["params"][0], "aa", "bb", "cc"]})
        _ = await read_msg(reader)

        writer.close()
        await writer.wait_closed()
    finally:
        await shutdown_system(system)


def test_integration_single_upstream_dual_authorize_and_routing() -> None:
    asyncio.run(integration_single_upstream_dual_authorize_and_routing())


def test_integration_fee_auth_failure_metric_increment() -> None:
    asyncio.run(integration_fee_auth_failure_metric_increment())


def test_integration_reject_logging_includes_upstream_error(caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.proxy")
    asyncio.run(integration_reject_logging_includes_upstream_error())
    assert any(
        "event=submit_result" in rec.message and "accepted=False" in rec.message and "error=[20, 'stale share', None]" in rec.message
        for rec in caplog.records
    )


def test_upstream_session_uses_main_upstream_only() -> None:
    cfg = Settings(
        fee_user="fee.wallet.worker",
        upstream_host="main.pool.local",
        upstream_primary_port=1001,
        upstream_secondary_port=1002,
        fee_upstream_host="fee.pool.local",
        fee_upstream_primary_port=2001,
        fee_upstream_secondary_port=2002,
    )
    session = UpstreamSession(cfg)
    assert session._host == "main.pool.local"
    assert session._ports == [1001, 1002]


def test_integration_runtime_failover_and_reconnect() -> None:
    async def _run() -> None:
        system = await setup_system()
        session = None
        try:
            cfg = Settings(
                fee_user="fee.wallet.worker",
                socks5_host="127.0.0.1",
                socks5_port=system["socks_port"],
                upstream_host="127.0.0.1",
                upstream_primary_port=system["pool_port"],
                upstream_secondary_port=system["pool_port"],
                reconnect_initial_backoff_seconds=0.05,
                reconnect_max_backoff_seconds=0.2,
                reconnect_attempts=2,
            )
            session = UpstreamSession(cfg)
            await session.connect()
            assert session.connected_port == cfg.upstream_primary_port
            ok = await session.reconnect_with_backoff()
            assert ok is True
            await session.close()
            assert session.writer is None
            assert session.reader is None
        finally:
            if session:
                await session.close()
            await shutdown_system(system)

    asyncio.run(_run())
