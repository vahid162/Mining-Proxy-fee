import asyncio
import json
from contextlib import suppress
from dataclasses import dataclass, field

from app.config import Settings
from app.proxy import MinerMetrics, MinerProxy


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

async def wait_for_condition(check, timeout: float = 3.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if check():
            return
        await asyncio.sleep(0.05)
    raise TimeoutError("condition not met")


@dataclass
class FakePool:
    name: str
    default_difficulty: float
    close_on_submit: bool = False
    authorize_success: bool = True
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
                    resp = {"id": mid, "result": [None, "aa", 4], "error": None}
                    await send_msg(writer, resp)
                elif method == "mining.authorize":
                    user = msg.get("params", [""])[0]
                    self.authorizations.append(user)
                    resp = {"id": mid, "result": self.authorize_success, "error": None}
                    await send_msg(writer, resp)
                elif method == "mining.submit":
                    user = msg.get("params", ["", ""])[0]
                    job_id = msg.get("params", ["", ""])[1]
                    self.submits.append((user, job_id))
                    resp = {"id": mid, "result": True, "error": None}
                    await send_msg(writer, resp)
                    if self.close_on_submit:
                        writer.close()
                        await writer.wait_closed()
                        return
                else:
                    resp = {"id": mid, "result": True, "error": None}
                    await send_msg(writer, resp)
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
        _ = await reader.readexactly(2)
        n_methods = _[1]
        await reader.readexactly(n_methods)
        writer.write(b"\x05\x00")
        await writer.drain()

        head = await reader.readexactly(4)
        atyp = head[3]
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
    close_primary_on_submit: bool = False,
    fee_authorize_success: bool = True,
    fee_path_startup_policy: str = "strict",
):
    primary_pool = FakePool("primary", default_difficulty=4.0, close_on_submit=close_primary_on_submit)
    secondary_pool = FakePool("secondary", default_difficulty=16.0, authorize_success=fee_authorize_success)

    primary_server = await asyncio.start_server(primary_pool.handle, "127.0.0.1", 0)
    secondary_server = await asyncio.start_server(secondary_pool.handle, "127.0.0.1", 0)
    primary_port = primary_server.sockets[0].getsockname()[1]
    secondary_port = secondary_server.sockets[0].getsockname()[1]

    socks_server = await asyncio.start_server(socks5_handler, "127.0.0.1", 0)
    socks_port = socks_server.sockets[0].getsockname()[1]

    fee_primary_port = secondary_port if not fee_authorize_success else primary_port
    fee_secondary_port = primary_port if not fee_authorize_success else secondary_port

    cfg = Settings(
        listen_host="127.0.0.1",
        listen_port=0,
        socks5_host="127.0.0.1",
        socks5_port=socks_port,
        upstream_host="127.0.0.1",
        upstream_primary_port=primary_port,
        upstream_secondary_port=secondary_port,
        fee_upstream_host="127.0.0.1",
        fee_upstream_primary_port=fee_primary_port,
        fee_upstream_secondary_port=fee_secondary_port,
        fee_user="fee.wallet.worker",
        fee_password="x",
        fee_ratio=0.05,
        rpc_timeout_seconds=2.0,
        upstream_read_timeout_seconds=0.3,
        write_timeout_seconds=2.0,
        reconnect_initial_backoff_seconds=0.05,
        reconnect_max_backoff_seconds=0.2,
        reconnect_attempts=20,
        max_pending_rpcs=64,
        fee_path_startup_policy=fee_path_startup_policy,
    )

    metrics = MinerMetrics()
    proxy = MinerProxy(cfg, metrics)
    proxy_server = await asyncio.start_server(proxy.handle, "127.0.0.1", 0)
    proxy_port = proxy_server.sockets[0].getsockname()[1]

    return {
        "primary_pool": primary_pool,
        "secondary_pool": secondary_pool,
        "primary_server": primary_server,
        "secondary_server": secondary_server,
        "socks_server": socks_server,
        "proxy_server": proxy_server,
        "proxy_port": proxy_port,
        "metrics": metrics,
    }


async def shutdown_system(system: dict) -> None:
    for key in ("proxy_server", "socks_server", "primary_server", "secondary_server"):
        srv = system[key]
        srv.close()
        await srv.wait_closed()


async def integration_flow_happy_path() -> None:
    system = await setup_system(close_primary_on_submit=False)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", system["proxy_port"])

        await send_msg(writer, {"id": 1, "method": "mining.subscribe", "params": []})
        sub_resp = await read_msg(reader)
        assert sub_resp["id"] == 1

        await send_msg(writer, {"id": 2, "method": "mining.authorize", "params": ["main.wallet.worker1", "x"]})
        auth_resp = await read_msg(reader)
        assert auth_resp["result"] is True

        await system["primary_pool"].broadcast_difficulty(2.0)
        await system["primary_pool"].broadcast_notify("job-main-1")
        await system["secondary_pool"].broadcast_difficulty(8.0)
        await system["secondary_pool"].broadcast_notify("job-fee-1")

        notify = await read_until_method(reader, "mining.notify")
        first_job_id = notify["params"][0]

        await send_msg(writer, {"id": 3, "method": "mining.submit", "params": ["main.wallet.worker1", first_job_id, "aa", "bb", "cc"]})
        submit_resp = await read_msg(reader)
        assert submit_resp["result"] is True

        await system["primary_pool"].broadcast_notify("job-next-2")
        notify2 = await read_until_method(reader, "mining.notify")
        second_job_id = notify2["params"][0]

        await send_msg(writer, {"id": 4, "method": "mining.submit", "params": ["main.wallet.worker1", second_job_id, "aa", "bb", "cc"]})
        submit_resp2 = await read_msg(reader)
        assert submit_resp2["result"] is True

        await wait_for_condition(lambda: len(system["primary_pool"].submits) + len(system["secondary_pool"].submits) >= 2)

        all_submit_users = [u for u, _ in (system["primary_pool"].submits + system["secondary_pool"].submits)]
        assert "fee.wallet.worker" in all_submit_users
        assert "main.wallet.worker1" in all_submit_users

        all_auth_users = system["primary_pool"].authorizations + system["secondary_pool"].authorizations
        assert "main.wallet.worker1" in all_auth_users
        assert "fee.wallet.worker" in all_auth_users

        snapshot = await system["metrics"].snapshot()
        assert snapshot["accepted_fee"] >= 1
        assert snapshot["accepted_main"] >= 1
        assert snapshot["accepted_fee_work"] > 0
        assert snapshot["accepted_main_work"] > 0

        writer.close()
        await writer.wait_closed()
    finally:
        await shutdown_system(system)


async def integration_failover_reconnect() -> None:
    system = await setup_system(close_primary_on_submit=False)
    session = None
    try:
        from app.proxy import UpstreamSession

        cfg = Settings(
            listen_host="127.0.0.1",
            listen_port=0,
            socks5_host="127.0.0.1",
            socks5_port=system["socks_server"].sockets[0].getsockname()[1],
            upstream_host="127.0.0.1",
            upstream_primary_port=system["primary_server"].sockets[0].getsockname()[1],
            upstream_secondary_port=system["secondary_server"].sockets[0].getsockname()[1],
            fee_upstream_host="127.0.0.1",
            fee_upstream_primary_port=system["primary_server"].sockets[0].getsockname()[1],
            fee_upstream_secondary_port=system["secondary_server"].sockets[0].getsockname()[1],
            fee_user="fee.wallet.worker",
            reconnect_initial_backoff_seconds=0.05,
            reconnect_max_backoff_seconds=0.2,
            reconnect_attempts=10,
        )

        session = UpstreamSession(cfg, "main")
        await session.connect()
        assert session.connected_port == cfg.upstream_primary_port

        await system["primary_pool"].drop_all()
        system["primary_server"].close()
        await system["primary_server"].wait_closed()

        ok = await session.reconnect_with_backoff()
        assert ok is True
        assert session.connected_port == cfg.upstream_secondary_port

        await session.close()
        assert session.writer is None
        assert session.reader is None
    finally:
        if session:
            await session.close()
        await shutdown_system(system)


def test_integration_happy_path_dual_upstream_and_difficulty() -> None:
    asyncio.run(integration_flow_happy_path())


def test_integration_runtime_failover_and_reconnect() -> None:
    asyncio.run(integration_failover_reconnect())


async def integration_job_mismatch_metric_increment() -> None:
    system = await setup_system(close_primary_on_submit=False)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", system["proxy_port"])

        await send_msg(writer, {"id": 1, "method": "mining.subscribe", "params": []})
        _ = await read_msg(reader)

        await send_msg(writer, {"id": 2, "method": "mining.authorize", "params": ["main.wallet.worker1", "x"]})
        _ = await read_msg(reader)

        await send_msg(writer, {"id": 3, "method": "mining.submit", "params": ["main.wallet.worker1", "unknown-job", "aa", "bb", "cc"]})
        submit_resp = await read_msg(reader)
        assert submit_resp["result"] is True

        snapshot = await system["metrics"].snapshot()
        assert snapshot["job_mismatch_count"] == 1

        writer.close()
        await writer.wait_closed()
    finally:
        await shutdown_system(system)


async def integration_auth_failures_fee_metric_increment() -> None:
    system = await setup_system(close_primary_on_submit=False, fee_authorize_success=False, fee_path_startup_policy="best_effort")
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", system["proxy_port"])

        await send_msg(writer, {"id": 1, "method": "mining.subscribe", "params": []})
        _ = await read_msg(reader)

        await send_msg(writer, {"id": 2, "method": "mining.authorize", "params": ["main.wallet.worker1", "x"]})
        auth_resp = await read_msg(reader)
        assert auth_resp["result"] is True

        snapshot = await system["metrics"].snapshot()
        assert snapshot["auth_failures_fee"] == 1

        writer.close()
        await writer.wait_closed()
    finally:
        await shutdown_system(system)



def test_integration_job_mismatch_metric_increment() -> None:
    asyncio.run(integration_job_mismatch_metric_increment())


def test_integration_auth_failures_fee_metric_increment() -> None:
    asyncio.run(integration_auth_failures_fee_metric_increment())


def test_upstream_session_uses_fee_specific_upstream() -> None:
    from app.proxy import UpstreamSession

    cfg = Settings(
        fee_user="fee.wallet.worker",
        upstream_host="main.pool.local",
        upstream_primary_port=1001,
        upstream_secondary_port=1002,
        fee_upstream_host="fee.pool.local",
        fee_upstream_primary_port=2001,
        fee_upstream_secondary_port=2002,
    )

    main_session = UpstreamSession(cfg, "main")
    fee_session = UpstreamSession(cfg, "fee")

    assert main_session._host == "main.pool.local"
    assert main_session._ports == [1001, 1002]
    assert fee_session._host == "fee.pool.local"
    assert fee_session._ports == [2001, 2002]
