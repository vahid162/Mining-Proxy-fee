# OPERATIONS Guide

این سند چک‌لیست روزانه اپراتور را برای اجرای پایدار سرویس می‌دهد.

## راه‌اندازی اپراتوری (۳ دستور)
```bash
cp .env.example .env
# تنظیم حداقل متغیرها: FEE_USER, FEE_RATIO, UPSTREAM_*, FEE_UPSTREAM_*
docker compose pull && docker compose up -d
```

## Health checks
```bash
docker compose ps
curl http://127.0.0.1:${METRICS_PORT:-9100}
```

## Logs
```bash
docker compose logs --tail=200 fee-proxy
docker compose logs -f fee-proxy
```

## Metrics (نمونه شاخص‌ها)
از endpoint متریک/سلامت:
```bash
curl http://127.0.0.1:${METRICS_PORT:-9100}
```

شاخص‌های مهم در پایش:
- `fee_ratio`
- `rejected_main` / `rejected_fee`
- `upstream_reconnects_*`
- `upstream_failovers_*`

## Backup: deploy/v2raya
پوشه `deploy/v2raya` state مربوط به v2rayA را نگه می‌دارد؛ قبل از تغییرات مهم از آن بکاپ بگیر:

```bash
tar -czf v2raya-backup-$(date +%F).tar.gz deploy/v2raya
```
