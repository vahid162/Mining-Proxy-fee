# Mining-Proxy-fee

`Mining-Proxy-fee` یک **Stratum-aware mining proxy** برای fee-routing است که به‌صورت Docker-ready برای اجرای تک‌سرور طراحی شده است.

## What it is
- مسیر fee-aware روی پورت `LISTEN_PORT` (پیش‌فرض `40040`) با حساب fee جدا (`FEE_USER`).
- مسیر forwarding ساده روی پورت `60046` (بدون ورود به منطق fee) برای fallback/rollback عملیاتی.
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
- `FEE_RATIO`
- `UPSTREAM_HOST`, `UPSTREAM_PRIMARY_PORT`, `UPSTREAM_SECONDARY_PORT`
- `FEE_UPSTREAM_HOST`, `FEE_UPSTREAM_PRIMARY_PORT`, `FEE_UPSTREAM_SECONDARY_PORT`

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
- `FEE_UPSTREAM_HOST`, `FEE_UPSTREAM_PRIMARY_PORT`, `FEE_UPSTREAM_SECONDARY_PORT`
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
- `V2RAYA_IMAGE`, `GOST_IMAGE`
- `V2RAYA_UI_BIND_HOST`, `V2RAYA_UI_PORT`
- `DOCKER_LOG_MAX_SIZE`, `DOCKER_LOG_MAX_FILE`

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
