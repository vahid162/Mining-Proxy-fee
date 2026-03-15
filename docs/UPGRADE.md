# UPGRADE Runbook

این راهنما مسیر استاندارد ارتقا برای اپراتور را نشان می‌دهد.

## 1) آماده‌سازی
1. از `.env` فعلی بکاپ بگیر.
2. نسخه target (tag) را مشخص کن.
3. اگر لازم بود، `compose.yaml` و `.env.example` همان release را جایگزین کن.

## 2) ارتقا
```bash
docker compose pull
docker compose up -d
```

## 3) اعتبارسنجی بعد از ارتقا
```bash
docker compose ps
docker compose logs --tail=200 fee-proxy
curl http://127.0.0.1:${METRICS_PORT:-9100}
```

## 4) rollback by tag (اگر لازم شد)
اگر ارتقا مشکل داشت، `APP_VERSION` را در `.env` به tag قبلی برگردان (مثلاً `v0.7.1`) و سپس:

```bash
docker compose pull
docker compose up -d
```
