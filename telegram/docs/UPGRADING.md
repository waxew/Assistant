# راهنمای ارتقا و انتشار نسخه بعدی

1. از PostgreSQL و `TOKEN_ENCRYPTION_KEY` بکاپ بگیرید.
2. تغییرات را در یک branch جدا انجام دهید و تست‌ها را اجرا کنید.
3. برای تغییر schema یک migration جدید بسازید؛ migration قدیمی را بازنویسی نکنید.
4. ابتدا روی کپی staging دیتابیس، `alembic upgrade head` و مسیرهای خرید/پرداخت را تست کنید.
5. image جدید Docker را بسازید، migration را اجرا کنید و سپس سرویس را restart کنید.
6. `/healthz`، لاگ ربات مادر و حداقل یک tenant را بررسی کنید.

## قرارداد سازگاری

- callback dataهای فعال را بدون migration مکالمه ناگهانی حذف نکنید.
- مقادیر enum دیتابیس را rename نکنید؛ مقدار جدید اضافه و داده قدیمی را migrate کنید.
- تغییر `tenant_id` یا کلیدهای خارجی باید با تست جداسازی داده بین فروشگاه‌ها همراه باشد.
- عملیات مالی باید idempotent و داخل transaction بماند.

## پیشنهادهای نسخه ۲

- Redis برای FSM و صف broadcast
- worker shard برای توزیع tenantها
- webhook اختصاصی به‌جای long polling در مقیاس بالا
- پنل وب برای گزارش‌گیری و تنظیمات
- object storage برای بکاپ‌ها و گزارش‌های دوره‌ای
- observability شامل Sentry/OpenTelemetry و متریک پرداخت

