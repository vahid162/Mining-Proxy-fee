# Mining-Proxy-fee

`Mining-Proxy-fee` یک **Stratum-aware mining proxy** برای fee-routing است که به‌صورت Docker-ready برای اجرای تک‌سرور طراحی شده است.

## What it is
- مسیر fee-aware روی پورت `LISTEN_PORT` (پیش‌فرض `40040`) با حساب fee جدا (`FEE_USER`).
- مسیر forwarding ساده روی پورت `60046` (بدون ورود به منطق fee) برای fallback/rollback عملیاتی.
- استقرار اپراتوری با Docker Compose و مصرف image آماده از GHCR.

## Quick Start (اپراتور نهایی)
1) از صفحه Release، فایل `release-bundle.tar.gz` را دانلود و extract کن.

2) فایل `.env` را از روی نمونه بساز و متغیرهای ضروری را تنظیم کن:

```bash
cp .env.example .env
```

3) استک را با image آماده بالا بیاور:

```bash
docker compose pull
docker compose up -d
```

بررسی سریع:

```bash
docker compose ps
docker compose logs --tail=200 fee-proxy
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

## Upgrade path
- مسیر ارتقا: `docs/UPGRADE.md`
- مسیر بازگشت (rollback): `docs/ROLLBACK.md`
- عملیات روزانه (health/logs/metrics/backup): `docs/OPERATIONS.md`

برای انتشار نسخه جدید:
```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

> روی هر tag از جنس `vX.Y.Z`، workflow release به‌صورت خودکار CI را اجرا می‌کند، imageها را روی GHCR منتشر می‌کند، Release Notes را از `CHANGELOG.md` می‌سازد و GitHub Release را همراه assetهای اپراتوری منتشر می‌کند.

## نکته برای توسعه
مسیر build-from-source فقط برای توسعه‌دهنده‌هاست و در راه‌اندازی اپراتوری استفاده نمی‌شود.

## License
This project is released under the MIT License.
