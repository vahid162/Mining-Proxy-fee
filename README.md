# Mining-Proxy-fee

`Mining-Proxy-fee` یک **Stratum-aware mining proxy** برای fee-routing است که به‌صورت Docker-ready برای اجرای تک‌سرور طراحی شده است.

## What it is
- مسیر fee-aware روی پورت `LISTEN_PORT` (پیش‌فرض `40040`) با **single-upstream + dual-authorize**: یک اتصال upstream، یک subscribe، و authorize جدا برای main/fee روی همان اتصال.
- مسیر forwarding ساده روی پورت `60046` فقط برای fallback/rollback عملیاتی (خارج از مسیر نرمال fee-aware).
- استقرار اپراتوری با Docker Compose و مصرف image آماده از GHCR.

## Quick Start (اپراتور نهایی)
1) از صفحه Release، فایل `release-bundle.tar.gz` را دانلود و extract کن.

2) فایل `.env` را از روی نمونه بساز:

```bash
cp .env.example .env
```

3) متغیرهای ضروری را تنظیم کن (بخش Minimal config پایین).

4) استک را با image آماده بالا بیاور:

```bash
docker compose -f compose.yaml pull
docker compose -f compose.yaml up -d
```

بررسی سریع:

```bash
docker compose -f compose.yaml ps
docker compose -f compose.yaml logs --tail=200 fee-proxy
curl http://127.0.0.1:${METRICS_PORT:-9100}
```

## Minimal config
برای شروع فقط این‌ها را تنظیم کن:
- `FEE_USER`
- `FEE_RATIO` (انتخاب مسیر fee/main فقط در سطح routing داخلی انجام می‌شود؛ upstream مشترک است)
- `UPSTREAM_HOST`, `UPSTREAM_PRIMARY_PORT`, `UPSTREAM_SECONDARY_PORT`

اختیاری (در صورت نیاز):
- `FORWARDER_UPSTREAM_HOST`, `FORWARDER_UPSTREAM_PORT`
- `LISTEN_PORT`, `METRICS_PORT`

## Environment variables (مطابق کامل `.env.example`)
### Runtime / Network
- `LISTEN_HOST`, `LISTEN_PORT`
- `SOCKS5_HOST`, `SOCKS5_PORT`
- `METRICS_HOST`, `METRICS_PORT`, `METRICS_BIND_HOST`

### Upstream routing
- `UPSTREAM_HOST`, `UPSTREAM_PRIMARY_PORT`, `UPSTREAM_SECONDARY_PORT`
- `FORWARDER_LISTEN_PORT`, `FORWARDER_UPSTREAM_HOST`, `FORWARDER_UPSTREAM_PORT`

### Auth / Fee control
- `MAIN_PASSWORD`
- `FEE_USER`, `FEE_PASSWORD`
- `FEE_RATIO`, `FEE_RATIO_SCOPE`, `FEE_PATH_STARTUP_POLICY`

### Reliability / Limits
- `MAX_SESSIONS`
- `RPC_TIMEOUT_SECONDS`, `UPSTREAM_READ_TIMEOUT_SECONDS`, `WRITE_TIMEOUT_SECONDS`
- `RECONNECT_INITIAL_BACKOFF_SECONDS`, `RECONNECT_MAX_BACKOFF_SECONDS`, `RECONNECT_ATTEMPTS`
- `MAX_PENDING_RPCS`

### Images / UI / Logging
- `APP_VERSION`, `FEE_PROXY_IMAGE`
- `V2RAYA_IMAGE`, `V2RAYA_CORE_BIN`, `GOST_IMAGE`
- `V2RAYA_UI_BIND_HOST`, `V2RAYA_UI_PORT`
- `DOCKER_LOG_MAX_SIZE`, `DOCKER_LOG_MAX_FILE`

`V2RAYA_CORE_BIN` به‌صورت پیش‌فرض روی `/usr/local/bin/v2ray` تنظیم می‌شود (v2ray-core). اگر بخواهی Xray استفاده کنی، مقدارش را `/usr/local/bin/xray` بگذار.


## مسیر پیش‌فرض و مسیر fallback برای SOCKS
مسیر canonical و پیش‌فرض پروژه **بدون تغییر** است:
- `fee-proxy -> v2raya:20170 -> upstream`
- مقدارهای پیش‌فرض `.env.example` هم باید همین بماند:
  - `SOCKS5_HOST=v2raya`
  - `SOCKS5_PORT=20170`

نمونه اجرای پیش‌فرض (canonical):

```bash
docker compose -f compose.yaml up -d
```

## Fallback برای loopback-only بودن listener های v2rayA
در بعضی استقرارهای Docker، v2rayA سرویس SOCKS را فقط روی `127.0.0.1:20170` داخل همان کانتینر bind می‌کند.
در این حالت healthcheck خود v2rayA سبز می‌شود، اما کانتینر sibling (مثل `fee-proxy`) نمی‌تواند به `v2raya:20170` وصل شود و خطای `connection refused` می‌بینی.

برای این سناریو، یک overlay اختیاری اضافه شده است: `compose.v2raya-bridge.yaml`.
این overlay یک sidecar با GOST بالا می‌آورد که با `network_mode: "service:v2raya"` داخل namespace شبکه v2raya اجرا می‌شود و این forward ها را می‌سازد:
- `22070 -> 127.0.0.1:20170`
- `22071 -> 127.0.0.1:20171`
- `22072 -> 127.0.0.1:20172`

> این مسیر فقط fallback است و مسیر canonical پیش‌فرض را عوض نمی‌کند.
> `compose.v2raya-bridge.yaml` به‌صورت پیش‌فرض داخل `compose.yaml` merge نشده و باید فقط در صورت نیاز با `-f compose.v2raya-bridge.yaml` فعال شود.
> در overlay هم عمداً `depends_on: condition: service_healthy` استفاده شده (نه `service_started`) تا با الگوی فعلی پروژه برای وابستگی به سلامت `v2raya` هم‌راستا بماند.

مراحل فعال‌سازی fallback:
1) `SOCKS5_HOST=v2raya` را همان‌طور نگه دار.
2) در `.env` مقدار `SOCKS5_PORT=22070` بگذار.
3) استک را با overlay بالا بیاور:

```bash
docker compose -f compose.yaml -f compose.v2raya-bridge.yaml up -d
```

راستی‌آزمایی ساده از داخل `fee-proxy`:

```bash
docker exec fee-proxy python -c "import os,socket; h=os.getenv('SOCKS5_HOST','v2raya'); p=int(os.getenv('SOCKS5_PORT','22070')); s=socket.create_connection((h,p),5); s.close(); print(f'OK {h}:{p}')"
```

یا از اسکریپت preflight سبک استفاده کن (با امکان override مستقیم host/port):

```bash
SOCKS5_HOST=v2raya SOCKS5_PORT=22070 ./deploy/check-socks-reachability.sh
```

## Troubleshooting (loopback-only listener)
اگر این تست fail شد:

```bash
docker exec fee-proxy python -c "import socket; socket.create_connection(('v2raya',20170),5)"
```

و داخل v2raya دیدی listener فقط loopback است:

```bash
docker exec v2raya ss -lntp | grep 20170
# نمونه مشکل: 127.0.0.1:20170
```

یعنی healthcheck فعلی فقط دسترسی loopback از داخل خود کانتینر v2raya را تایید می‌کند، نه دسترسی از sibling container ها.
در این وضعیت overlay زیر را فعال کن:

```bash
docker compose -f compose.yaml -f compose.v2raya-bridge.yaml up -d
```

## Upgrade path
- مسیر ارتقا: `docs/UPGRADE.md`
- مسیر بازگشت (rollback): `docs/ROLLBACK.md`
- عملیات روزانه (health/logs/metrics/backup): `docs/OPERATIONS.md`

برای انتشار نسخه جدید:
1) قبل از ساخت tag این تمیزکاری کوتاه را انجام بده تا release pipeline به‌خاطر ناهماهنگی‌ها fail نشود:

```bash
# 1) نسخه جاری را چک کن
cat VERSION

# 2) مطمئن شو CHANGELOG.md برای همین نسخه یک سکشن "## X.Y.Z" دارد
# (اگر نسخه X.Y.Z است، باید "## X.Y.Z" وجود داشته باشد)

# 3) چک‌های محلی pipeline را اجرا کن
cp .env.example .env
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
docker compose -f compose.yaml config
docker compose -f compose.yaml -f compose.dev.yaml config
```

2) tag را دقیقاً برابر VERSION بساز و جداگانه روی GitHub push کن:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

> روی هر tag از جنس `vX.Y.Z`، workflow release به‌صورت خودکار CI را اجرا می‌کند، imageها را روی GHCR منتشر می‌کند، Release Notes را از `CHANGELOG.md` می‌سازد و GitHub Release را همراه assetهای اپراتوری منتشر می‌کند. چون trigger روی `push.tags` تنظیم شده، تا وقتی `git push origin vX.Y.Z` انجام نشود release واقعی شروع نمی‌شود.

> نام canonical فایل‌های Compose در این ریپو `compose.yaml` (اپراتوری) و `compose.dev.yaml` (development overlay) است و `docker-compose.yml` در مسیر رسمی پروژه استفاده نمی‌شود.

> قبل از tag همیشه نسخه را از فایل `VERSION` بخوان و همان را tag کن (مثال: اگر `VERSION=X.Y.Z` است، tag باید `vX.Y.Z` باشد).

## نکته برای توسعه
مسیر build-from-source فقط برای توسعه‌دهنده‌هاست و در راه‌اندازی اپراتوری استفاده نمی‌شود.

## License
This project is released under the MIT License.
