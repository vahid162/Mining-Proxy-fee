#!/usr/bin/env bash
set -euo pipefail

FEE_PROXY_CONTAINER="${FEE_PROXY_CONTAINER:-fee-proxy}"
SOCKS5_HOST="${SOCKS5_HOST:-v2raya}"
SOCKS5_PORT="${SOCKS5_PORT:-20170}"

printf '[1/2] DNS check in %s for host %s\n' "$FEE_PROXY_CONTAINER" "$SOCKS5_HOST"
docker exec \
  -e SOCKS5_HOST="$SOCKS5_HOST" \
  "$FEE_PROXY_CONTAINER" \
  python - <<'PY'
import os, socket
host = os.environ["SOCKS5_HOST"]
print(socket.gethostbyname(host))
PY

printf '[2/2] TCP check in %s to %s:%s\n' "$FEE_PROXY_CONTAINER" "$SOCKS5_HOST" "$SOCKS5_PORT"
docker exec \
  -e SOCKS5_HOST="$SOCKS5_HOST" \
  -e SOCKS5_PORT="$SOCKS5_PORT" \
  "$FEE_PROXY_CONTAINER" \
  python - <<'PY'
import os, socket
host = os.environ["SOCKS5_HOST"]
port = int(os.environ["SOCKS5_PORT"])
with socket.create_connection((host, port), timeout=5):
    pass
print(f"OK {host}:{port}")
PY

echo 'SOCKS preflight checks passed.'
