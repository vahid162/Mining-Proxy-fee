# OPERATIONS Guide

این سند چک‌لیست روزانه اپراتوری را خلاصه می‌کند.

## راه‌اندازی اپراتوری
```bash
cp .env.example .env
# ویرایش .env
docker compose pull
docker compose up -d
```

## پایش سریع
```bash
docker compose ps
docker compose logs --tail=200 fee-proxy
curl http://127.0.0.1:${METRICS_PORT:-9100}
```

## توقف/راه‌اندازی مجدد
```bash
docker compose down
docker compose up -d
```

## فایل‌های مهم release
- `compose.yaml`
- `.env.example`
- `CHANGELOG.md`
- `checksums.txt`
- `release-bundle.tar.gz`
