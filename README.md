# Telegram File Bot

ربات تلگرام برای دریافت فایل‌های حجیم (تا ۲ گیگابایت)، ذخیره روی سرور و ارائه لینک مستقیم دانلود + پنل مدیریت وب.

## امکانات

- دریافت فایل تا **۲ گیگابایت** از تلگرام (با Pyrogram)
- پشتیبانی از ارسال لینک مستقیم برای دانلود
- لینک دانلود مستقیم و دائمی
- پنل مدیریت وب روی پورت **14141**
- نوار پیشرفت زنده در تلگرام
- نصب با **یک دستور تک‌خطی**

## نصب سریع (یک خط)

```bash
bash <(curl -Ls https://raw.githubusercontent.com/arefhere51/telegram_file_bot/main/install.sh)
```

کلون مخزن عمومی با HTTPS انجام می‌شود و به نام کاربری/رمز GitHub نیازی ندارد. نصب‌کننده اطلاعات تلگرام و ورود جداگانهٔ پنل وب را می‌پرسد.

برای محیط‌های Docker / بدون systemd:

```bash
bash <(curl -Ls https://raw.githubusercontent.com/arefhere51/telegram_file_bot/main/install.sh) --mode foreground
```

## پیش‌نیازها

1. **API_ID و API_HASH** از [my.telegram.org](https://my.telegram.org)
2. **توکن ربات** از [@BotFather](https://t.me/BotFather)
3. **آیدی عددی** خودتان (با [@userinfobot](https://t.me/userinfobot) بگیرید)
4. **نام کاربری و رمز پنل وب** (برای ورود به پنل؛ مستقل از تلگرام و GitHub)

## استفاده

1. فایل را برای ربات بفرستید (یا لینک مستقیم بفرستید)
2. ربات دانلود می‌کند و لینک مستقیم می‌دهد
3. پنل مدیریت: `http://IP:14141` (نیازمند نام کاربری و رمز پنل که هنگام نصب تنظیم کرده‌اید). برای استفاده از اینترنت، پنل را پشت HTTPS قرار دهید؛ احراز هویت پنل از HTTP Basic استفاده می‌کند.

## دستورات ربات

| دستور   | توضیح              |
|---------|--------------------|
| /start  | شروع               |
| /list   | لیست آخرین فایل‌ها |
| /stats  | آمار فضای مصرفی    |
| /help   | راهنما             |

## ساختار

```
telegram_file_bot/
├── main.py          # نقطه شروع (ربات + وب)
├── bot.py           # منطق ربات Pyrogram
├── web_app.py       # پنل FastAPI
├── config.py
├── database.py
├── templates/
├── install.sh       # نصب‌کننده تک‌دستوری
└── requirements.txt
```

## لایسنس

MIT
