from __future__ import annotations

import asyncio
import json
import logging
import signal

from .config import Settings
from .proxy import MinerMetrics, MinerProxy


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    )


async def metrics_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, metrics: MinerMetrics) -> None:
    await reader.read(2048)
    body = json.dumps(await metrics.snapshot()).encode()
    response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        + f"Content-Length: {len(body)}\r\n".encode()
        + b"Connection: close\r\n\r\n"
        + body
    )
    writer.write(response)
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def run() -> None:
    setup_logging()
    cfg = Settings.from_env()
    metrics = MinerMetrics()
    proxy = MinerProxy(cfg, metrics)

    miner_server = await asyncio.start_server(proxy.handle, cfg.listen_host, cfg.listen_port)
    metrics_server = await asyncio.start_server(
        lambda r, w: metrics_handler(r, w, metrics),
        cfg.metrics_host,
        cfg.metrics_port,
    )

    logging.info("miner_proxy_listen=%s:%s", cfg.listen_host, cfg.listen_port)
    logging.info("metrics_listen=%s:%s", cfg.metrics_host, cfg.metrics_port)

    stop = asyncio.Event()

    def _stop() -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _stop)

    await stop.wait()
    miner_server.close()
    metrics_server.close()
    await miner_server.wait_closed()
    await metrics_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(run())
