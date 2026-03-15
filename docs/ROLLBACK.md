# ROLLBACK Runbook

اگر بعد از release جدید مشکل دیدی، این مسیر rollback را اجرا کن.

## 1) کنترل فوری ترافیک
- اگر افت کیفیت/افزایش reject دیدی، ماینرهای canary را موقتاً به مسیر ساده `60046` برگردان.
- مسیر `60046` فقط forwarding ساده است و در منطق fee وارد نمی‌شود.

## 2) بازگشت به image نسخه قبلی
1. در `.env` مقدار `APP_VERSION` را به tag پایدار قبلی تغییر بده (مثلاً `v0.7.1`).
2. سپس سرویس را با image قبلی بالا بیاور:

```bash
docker compose pull
docker compose up -d
```

## 3) بررسی وضعیت بعد از rollback
```bash
docker compose ps
docker compose logs --tail=200 fee-proxy
curl http://127.0.0.1:${METRICS_PORT:-9100}
```
