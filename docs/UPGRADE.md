# UPGRADE Runbook

این راهنما برای ارتقا از یک نسخه release به نسخه جدید است.

## مراحل
1. از `.env` فعلی بکاپ بگیر.
2. Assetهای release جدید را دریافت کن (`compose.yaml`, `.env.example`, `release-bundle.tar.gz`).
3. `.env.example` جدید را با `.env` فعلی مقایسه کن و فقط متغیرهای جدید/تغییر یافته را اعمال کن.
4. image جدید را دریافت و سرویس را بالا بیاور:
   ```bash
   docker compose pull
   docker compose up -d
   ```
5. سلامت سرویس را بررسی کن:
   ```bash
   docker compose ps
   docker compose logs --tail=200 fee-proxy
   curl http://127.0.0.1:${METRICS_PORT:-9100}
   ```

## معیار پذیرش
- `fee-proxy` در وضعیت healthy باشد.
- نرخ reject غیرعادی مشاهده نشود.
- متریک `fee_ratio` نزدیک مقدار هدف باشد.
