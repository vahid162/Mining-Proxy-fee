# Mining-Proxy-fee

پروژه `Mining-Proxy-fee` یک **Stratum-aware mining proxy** به زبان Python است که برای سناریوی fee-routing طراحی شده است.

## ویژگی‌ها
- دریافت اتصال ماینر روی پورت `40040`
- اتصال outbound به ViaBTC از طریق SOCKS5 (`v2rayA`)
- حفظ اکانت اصلی از خود ماینر (دیگر `MAIN_USER` سراسری ندارد)
- مسیر fee با اکانت جدا (`FEE_USER`)
- کنترل نسبت fee با هدف پیش‌فرض `5%` بر مبنای accepted difficulty/work
- failover پویا بین پورت‌های `3333` و `443`
- endpoint متریک/سلامت روی `9100`
- جداسازی پورت fee (`40040`) از پورت forwarding ساده (`60046`) در Compose
- اجرای کامل با Docker Compose

## معماری

```text
(پورت feeدار 40040)
Miner -> fee-proxy (Python, Stratum-aware) -> v2rayA SOCKS5 -> ViaBTC

(پورت forwarding ساده 60046 - اختیاری)
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
- در ماینر، اکانت اصلی کاربر را همان‌طور که هست قرار بده

3) استک را بالا بیاور:

```bash
docker compose up -d --build
```

اگر پورت forwarding ساده (`60046`) را هم می‌خواهی:

```bash
docker compose --profile forwarder up -d
```

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
curl http://127.0.0.1:9100
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

## توسعه محلی و تست

```bash
python -m pytest -q
```

## نسخه
نسخه فعلی در فایل `VERSION` نگهداری می‌شود.


## مرزبندی محصول (خیلی مهم)
- Compose فقط orchestration می‌دهد (شبکه/health/lifecycle).
- منطق correctness شامل `fee ratio`, `session state`, `job routing` باید داخل `fee-proxy` باشد (و همین‌طور پیاده‌سازی شده).
- `simple-forwarder` عمداً Stratum-aware نیست و فقط برای پورت‌های non-fee استفاده می‌شود.
