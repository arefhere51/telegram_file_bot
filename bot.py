import asyncio
import os
import time
import re
from pathlib import Path
from typing import Optional

from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

from config import settings
from database import init_db, add_file, get_file, list_files, count_files, total_size, soft_delete, hard_delete

# Initialize DB
init_db()

app = Client(
    "filebot",
    api_id=settings.API_ID,
    api_hash=settings.API_HASH,
    bot_token=settings.BOT_TOKEN,
    workdir=str(settings.data_path),
)


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


def safe_filename(name: str, fallback: str = "download") -> str:
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "_", name).strip(" .")
    return (name or fallback)[:240]


def human_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def progress_bar(current: int, total: int, length: int = 12) -> str:
    if total == 0:
        return "░" * length
    filled = int(length * current / total)
    return "█" * filled + "░" * (length - filled)


@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply_text("⛔ شما اجازه استفاده از این ربات را ندارید.")
        return

    text = (
        "👋 **ربات دانلود فایل حجیم**\n\n"
        "فایل‌های تا **۲ گیگابایت** را بفرستید یا لینک مستقیم بفرستید.\n\n"
        "**دستورات:**\n"
        "/start - شروع\n"
        "/list - لیست فایل‌ها\n"
        "/stats - آمار فضای ذخیره‌سازی\n"
        "/help - راهنما\n\n"
        f"🌐 پنل مدیریت: `{settings.PUBLIC_BASE_URL}`"
    )
    await message.reply_text(text)


@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    text = (
        "📖 **راهنما**\n\n"
        "۱. هر فایلی (تا ۲ گیگ) را مستقیم برای ربات بفرستید.\n"
        "۲. ربات آن را دانلود و ذخیره می‌کند و لینک مستقیم می‌دهد.\n"
        "۳. لینک مستقیم را می‌توانید با هر کسی به اشتراک بگذارید.\n\n"
        "پنل وب روی پورت ۱۴۱۴۱ برای مدیریت فایل‌ها در دسترس است."
    )
    await message.reply_text(text)


@app.on_message(filters.command("stats") & filters.private)
async def stats_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    total = total_size()
    count = count_files()
    await message.reply_text(
        f"📊 **آمار**\n\n"
        f"تعداد فایل‌ها: `{count}`\n"
        f"حجم کل: `{human_size(total)}`"
    )


@app.on_message(filters.command("list") & filters.private)
async def list_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    files = list_files(limit=20)
    if not files:
        await message.reply_text("هنوز فایلی ذخیره نشده.")
        return

    lines = ["📁 **آخرین فایل‌ها:**\n"]
    for f in files:
        lines.append(
            f"• `{f['original_name']}` — {human_size(f['size'])}\n"
            f"  `{settings.PUBLIC_BASE_URL}/d/{f['id']}`"
        )
    await message.reply_text("\n".join(lines))


@app.on_message(filters.private & (filters.document | filters.video | filters.audio | filters.photo))
async def file_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply_text("⛔ دسترسی ندارید.")
        return

    # Determine media
    media = message.document or message.video or message.audio or message.photo
    if not media:
        return

    # For photo, take the largest
    if message.photo:
        file_size = message.photo.file_size or 0
        file_name = safe_filename(f"photo_{message.photo.file_unique_id}.jpg")
        mime = "image/jpeg"
    else:
        file_size = media.file_size or 0
        file_name = safe_filename(getattr(media, "file_name", None) or f"file_{media.file_unique_id}")
        mime = getattr(media, "mime_type", None)

    if file_size > settings.max_file_size_bytes:
        await message.reply_text(
            f"❌ فایل بزرگ‌تر از حد مجاز است.\n"
            f"حداکثر: {settings.MAX_FILE_SIZE_GB} GB\n"
            f"حجم فایل: {human_size(file_size)}"
        )
        return

    status = await message.reply_text("⬇️ در حال آماده‌سازی دانلود...")

    start_time = time.time()
    last_update = 0

    async def progress(current, total):
        nonlocal last_update
        now = time.time()
        if now - last_update < 2 and current != total:
            return
        last_update = now
        percent = (current / total * 100) if total else 0
        speed = current / (now - start_time + 0.001)
        eta = (total - current) / speed if speed > 0 else 0
        bar = progress_bar(current, total)
        try:
            await status.edit_text(
                f"⬇️ **در حال دانلود**\n\n"
                f"`{bar}` {percent:.1f}%\n"
                f"حجم: {human_size(current)} / {human_size(total)}\n"
                f"سرعت: {human_size(int(speed))}/s\n"
                f"زمان تقریبی: {int(eta)} ثانیه"
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            pass

    try:
        # Download to temp then move
        temp_path = settings.files_path / f"tmp_{message.id}_{file_name}"
        downloaded = await message.download(
            file_name=str(temp_path),
            progress=progress,
        )

        if not downloaded or not Path(downloaded).exists():
            await status.edit_text("❌ دانلود ناموفق بود.")
            return

        final_size = Path(downloaded).stat().st_size
        stored_name = f"{int(time.time())}_{__import__('uuid').uuid4().hex}_{file_name}"
        final_path = settings.files_path / stored_name
        Path(downloaded).rename(final_path)

        file_id = add_file(
            original_name=file_name,
            stored_name=stored_name,
            size=final_size,
            mime_type=mime,
            uploaded_by=message.from_user.id,
        )

        download_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/d/{file_id}"

        await status.edit_text(
            f"✅ **فایل ذخیره شد**\n\n"
            f"📄 نام: `{file_name}`\n"
            f"📦 حجم: `{human_size(final_size)}`\n\n"
            f"🔗 **لینک مستقیم:**\n`{download_url}`\n\n"
            f"می‌توانید این لینک را کپی کنید و به اشتراک بگذارید."
        )

    except Exception as e:
        await status.edit_text(f"❌ خطا در دانلود:\n`{str(e)[:300]}`")


@app.on_message(filters.private & filters.text & ~filters.command(["start", "help", "list", "stats"]))
async def text_handler(client: Client, message: Message):
    """Accept direct download URLs"""
    if not is_admin(message.from_user.id):
        return

    text = message.text.strip()
    if not (text.startswith("http://") or text.startswith("https://")):
        return

    # Only fetch public HTTP(S) destinations; do not allow SSRF to internal services.
    status = await message.reply_text("⬇️ در حال دانلود از لینک...")

    try:
        import httpx
        import socket
        import ipaddress
        from urllib.parse import urlparse, unquote

        parsed_url = urlparse(text)
        if parsed_url.scheme not in ("http", "https") or not parsed_url.hostname or parsed_url.username or parsed_url.password:
            raise ValueError("فقط URL عمومی HTTP/HTTPS معتبر پذیرفته می‌شود")
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(parsed_url.hostname, parsed_url.port or (443 if parsed_url.scheme == "https" else 80), type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise ValueError("دامنه قابل resolve نیست") from exc
        if not addresses or any(not ipaddress.ip_address(addr).is_global for addr in addresses):
            raise ValueError("دانلود از آدرس‌های داخلی یا غیرعمومی مجاز نیست")

        async with httpx.AsyncClient(follow_redirects=False, timeout=httpx.Timeout(60.0, read=60.0)) as http:
            async with http.stream("GET", text) as resp:
                if resp.status_code != 200:
                    await status.edit_text(f"❌ خطای HTTP: {resp.status_code}")
                    return

                content_length = int(resp.headers.get("content-length", 0))
                if content_length > settings.max_file_size_bytes:
                    await status.edit_text("❌ فایل بزرگ‌تر از حد مجاز است.")
                    return

                # Refuse redirects so a public URL cannot redirect the bot to localhost/private services.
                if resp.is_redirect:
                    await status.edit_text("❌ لینک‌های تغییرمسیر (redirect) پشتیبانی نمی‌شوند؛ لینک مستقیم را بفرستید.")
                    return

                cd = resp.headers.get("content-disposition", "")
                file_name = ""
                if "filename*=" in cd.lower():
                    import re
                    match = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.IGNORECASE)
                    if match:
                        file_name = unquote(match.group(1))
                if not file_name and "filename=" in cd.lower():
                    file_name = cd.split("filename=", 1)[1].strip().strip('"\' ')
                if not file_name:
                    file_name = unquote(Path(urlparse(text).path).name)
                file_name = safe_filename(file_name, f"download_{int(time.time())}")
                stored_name = f"{int(time.time())}_{__import__('uuid').uuid4().hex}_{file_name}"
                final_path = settings.files_path / stored_name
                temp_path = final_path.with_suffix(final_path.suffix + ".part")

                downloaded = 0
                start_time = time.time()
                last_update = 0

                with open(temp_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                        downloaded += len(chunk)
                        if downloaded > settings.max_file_size_bytes:
                            raise ValueError("حجم فایل از حد مجاز بیشتر است")
                        f.write(chunk)
                        now = time.time()
                        if now - last_update > 2:
                            last_update = now
                            total = content_length or downloaded
                            percent = (downloaded / total * 100) if total else 0
                            speed = downloaded / (now - start_time + 0.001)
                            bar = progress_bar(downloaded, total)
                            try:
                                await status.edit_text(
                                    f"⬇️ **در حال دانلود از لینک**\n\n"
                                    f"`{bar}` {percent:.1f}%\n"
                                    f"{human_size(downloaded)}"
                                    + (f" / {human_size(total)}" if content_length else "")
                                    + f"\nسرعت: {human_size(int(speed))}/s"
                                )
                            except Exception:
                                pass
                temp_path.replace(final_path)

        final_size = final_path.stat().st_size
        file_id = add_file(
            original_name=file_name,
            stored_name=stored_name,
            size=final_size,
            mime_type=None,
            uploaded_by=message.from_user.id,
        )
        download_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/d/{file_id}"

        await status.edit_text(
            f"✅ **فایل ذخیره شد**\n\n"
            f"📄 نام: `{file_name}`\n"
            f"📦 حجم: `{human_size(final_size)}`\n\n"
            f"🔗 **لینک مستقیم:**\n`{download_url}`"
        )

    except Exception as e:
        try:
            if "temp_path" in locals() and temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass
        try:
            await status.edit_text(f"❌ خطا:\n`{str(e)[:300]}`")
        except Exception:
            pass


async def main():
    print("🤖 Bot is starting...")
    await app.start()
    me = await app.get_me()
    print(f"✅ Bot started as @{me.username}")
    # Keep running
    await asyncio.Event().wait()


if __name__ == "__main__":
    app.run()
