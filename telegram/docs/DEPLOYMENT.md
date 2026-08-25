# استقرار production

## حداقل پیشنهادی

- Ubuntu 24.04 یا سرویس Docker سازگار
- PostgreSQL 16 یا 17
- دامنه HTTPS با reverse proxy مانند Caddy/Nginx
- 1 vCPU و 1GB RAM برای شروع؛ مصرف دقیق به تعداد ربات‌ها و ترافیک وابسته است

## چک‌لیست

1. `.env.example` را به `.env` کپی و همه مقادیر نمونه را عوض کنید.
2. برای دیتابیس و کاربر PostgreSQL رمز قوی جدا بسازید.
3. دامنه HTTPS را به پورت `WEB_PORT` برنامه proxy کنید.
4. `docker compose up -d --build` را اجرا کنید.
5. خروجی `/healthz` و `docker compose logs app` را بررسی کنید.
6. در ربات مادر یک ربات آزمایشی بسازید؛ محصول، پرداخت تست و بکاپ را از ابتدا تا انتها آزمایش کنید.
7. بکاپ زمان‌بندی‌شده PostgreSQL و کلید Fernet را در محل دیگری نگه دارید.

## نمونه Caddy

```caddyfile
bot.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

## متغیرهای حساس

`BUILDER_BOT_TOKEN`، `TOKEN_ENCRYPTION_KEY`، رمز دیتابیس و Merchant ID را در secret manager نگه دارید. تعویض Fernet key بدون فرآیند re-encrypt باعث توقف tenantهای قبلی می‌شود.

## عیب‌یابی سریع

- `Conflict: terminated by other getUpdates`: همان توکن در پردازش دیگری polling می‌شود؛ نمونه قبلی را متوقف کنید.
- ربات tenant شروع نمی‌شود: وضعیت اشتراک، `last_error` در دیتابیس و اعتبار توکن را بررسی کنید.
- عضویت اجباری کار نمی‌کند: tenant bot را ادمین کانال کنید و `@username` کانال را درست ثبت کنید.
- callback زرین‌پال نمی‌رسد: HTTPS، DNS، `PUBLIC_BASE_URL` و مسیر reverse proxy را بررسی کنید.

