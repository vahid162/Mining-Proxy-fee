# Mining-Proxy-fee

پروژه `Mining-Proxy-fee` یک **Stratum-aware mining proxy** به زبان Python است که برای سناریوی fee-routing طراحی شده است.

## ویژگی‌ها
- دریافت اتصال ماینر روی پورت قابل تنظیم `LISTEN_PORT` (پیش‌فرض `40040`)
- اتصال outbound به ViaBTC از طریق SOCKS5 (`v2rayA`) برای مسیر main و fee
- حفظ اکانت اصلی از خود ماینر (دیگر `MAIN_USER` سراسری ندارد)
- مسیر fee با اکانت جدا (`FEE_USER`)
- کنترل نسبت fee با هدف پیش‌فرض `5%` بر مبنای accepted difficulty/work
- failover پویا بین پورت‌های primary/secondary برای main و fee (با امکان upstream جدا برای fee)
- endpoint متریک/سلامت روی `METRICS_PORT` (پیش‌فرض `9100`)
- جداسازی پورت fee (`40040`) از پورت forwarding ساده (`60046`) در Compose
- اجرای کامل با Docker Compose

## معماری

```text
(پورت feeدار قابل تنظیم با LISTEN_PORT)
Miner -> fee-proxy (Python, Stratum-aware) -> v2rayA SOCKS5 -> ViaBTC(main/fee upstream configurable)

(پورت forwarding ساده 60046 - همیشه جدا از fee-proxy)
Miner -> simple-forwarder(gost) -> v2rayA SOCKS5 -> ViaBTC
```

## پیش‌نیازها
- Docker
- Docker Compose Plugin (`docker compose`)

## راه‌اندازی سریع

1) فایل env بساز:

```bash
cp .env.example .env
```

2) مقادیر مهم را در `.env` تنظیم کن:
- `FEE_USER` (اکانت fee)
- `FEE_RATIO` (نسبت fee مثل `0.05` یا `0.1`)
- `UPSTREAM_HOST/UPSTREAM_PRIMARY_PORT/UPSTREAM_SECONDARY_PORT` برای مسیر main
- `FEE_UPSTREAM_HOST/FEE_UPSTREAM_PRIMARY_PORT/FEE_UPSTREAM_SECONDARY_PORT` برای مسیر fee (در صورت نیاز به pool/domain جدا)
- `LISTEN_PORT` و `METRICS_PORT` برای پورت‌های fee-proxy
- `MAIN_USER` لازم نیست (main user از `mining.authorize` ورودی خوانده می‌شود)
- در ماینر، اکانت اصلی کاربر را همان‌طور که هست قرار بده

3) استک را بالا بیاور:

```bash
docker compose up -d --build
```

پورت forwarding ساده (`60046`) هم به‌صورت پیش‌فرض با استک بالا می‌آید و وارد منطق fee نمی‌شود.

4) وضعیت سرویس‌ها:

```bash
docker compose ps
```

5) لاگ زنده:

```bash
docker compose logs -f fee-proxy
```

6) بررسی health/metrics:

```bash
curl http://127.0.0.1:${METRICS_PORT:-9100}
```

## توقف / راه‌اندازی مجدد

```bash
docker compose down
docker compose up -d
```

## نکات عملیاتی مهم
- پورت SOCKS (`20170`) فقط داخل شبکه compose استفاده می‌شود.
- قبل از production، با canary rollout شروع کن.
- اگر reject rate بالا رفت، سریع rollback کن (مسیر قبلی forwarding ساده).
- نسبت fee بر پایه difficulty-weighted accepted work محاسبه می‌شود (دقیق‌تر از count خام).

## پیش‌نیاز مسیر volume برای v2rayA
چون در Compose این mount وجود دارد:

```yaml
./deploy/v2raya:/etc/v2raya
```

لازم است مسیر `deploy/v2raya` داخل ریپو وجود داشته باشد. این مسیر در پروژه اضافه شده است و state/config مربوط به v2rayA را روی host نگه می‌دارد (برای persistence).

## توسعه محلی و تست

```bash
python -m pytest -q
```

## نسخه
نسخه فعلی در فایل `VERSION` نگهداری می‌شود.


## مرزبندی محصول (خیلی مهم)
- `60046` فقط forwarding ساده است و وارد منطق fee در `fee-proxy` نمی‌شود.
- Compose فقط orchestration می‌دهد (شبکه/health/lifecycle).
- منطق correctness شامل `fee ratio`, `session state`, `job routing` باید داخل `fee-proxy` باشد (و همین‌طور پیاده‌سازی شده).
- `simple-forwarder` عمداً Stratum-aware نیست و فقط برای پورت‌های non-fee استفاده می‌شود.


## Canary Rollout (قدم‌به‌قدم)
1) **آماده‌سازی**
- از `.env` بکاپ بگیر و مطمئن شو `FEE_USER` درست تنظیم شده.
- ابتدا فقط سرویس fee-proxy را بالا بیاور: `docker compose up -d --build fee-proxy`

2) **شروع با درصد کم ماینرها**
- فقط 5% تا 10% ماینرها را موقتاً به پورت fee (پیش‌فرض `40040` یا مقدار `LISTEN_PORT`) بفرست.
- بقیه ماینرها روی مسیر قبلی یا `60046` (forwarding ساده) بمانند.

3) **پایش 15 تا 30 دقیقه‌ای**
- لاگ زنده: `docker compose logs -f fee-proxy`
- متریک: `curl http://127.0.0.1:${METRICS_PORT:-9100}`
- شاخص‌های حیاتی: `rejected_main/rejected_fee`, `upstream_reconnects_*`, `upstream_failovers_*`, `fee_ratio`

4) **افزایش تدریجی**
- اگر reject rate غیرعادی نبود، ترافیک را مرحله‌ای زیاد کن (مثلاً 10% → 25% → 50% → 100%).
- بین هر مرحله حداقل 10 تا 20 دقیقه پایش انجام بده.

5) **Rollback فوری (اگر مشکل دیدی)**
- فوراً ماینرهای canary را به مسیر قبلی برگردان.
- در صورت نیاز سرویس را پایین بیاور: `docker compose down`
- لاگ و snapshot متریک را برای عیب‌یابی نگه دار.
