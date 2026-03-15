# Mining-Proxy-fee

`Mining-Proxy-fee` یک **Stratum-aware mining proxy** برای fee-routing است که به‌صورت Docker-ready برای اجرای تک‌سرور طراحی شده است.

## What it is
- مسیر fee-aware روی پورت `LISTEN_PORT` (پیش‌فرض `40040`) با حساب fee جدا (`FEE_USER`).
- مسیر forwarding ساده روی پورت `60046` (بدون ورود به منطق fee) برای fallback/rollback عملیاتی.
- استقرار اپراتوری با Docker Compose و مصرف image آماده از GHCR.

## Quick Start (۳ دستور اپراتوری)
1) فایل env را بساز:

```bash
cp .env.example .env
```

2) متغیرهای ضروری را در `.env` تنظیم کن.

3) استک را بالا بیاور:

```bash
docker compose pull && docker compose up -d
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

## Development (build از سورس)
برای توسعه محلی:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
```

تست کد:

```bash
python -m pytest -q
```


## License
This project is released under the MIT License.
