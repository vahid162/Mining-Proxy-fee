# ROLLBACK Runbook

اگر بعد از ارتقا مشکل دیدی، این مسیر rollback را اجرا کن.

## مراحل
1. فایل‌های release نسخه قبلی را آماده کن.
2. `.env` نسخه پایدار قبلی را برگردان (اگر تغییر داده بودی).
3. به نسخه قبلی برگرد:
   ```bash
   docker compose pull
   docker compose up -d
   ```
4. سرویس را پایش کن:
   ```bash
   docker compose ps
   docker compose logs --tail=200 fee-proxy
   ```

## نکته عملیاتی
- اگر rollback فوری لازم است، ابتدا ماینرهای canary را به مسیر ساده (`60046`) برگردان.
