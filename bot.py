import os
import logging
import asyncio
from datetime import datetime
import pytz

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from scraper import fetch_funding_news
from formatter import format_report

# --- Config ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Boring Grinder Funding Bot đang chạy!\n\n"
        "Lệnh có thể dùng:\n"
        "/funding — Fetch danh sách funding mới nhất ngay bây giờ\n"
        "/help — Hướng dẫn sử dụng"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Hướng dẫn:\n\n"
        "/funding — Lấy danh sách các dự án gọi vốn mới nhất\n\n"
        "Bot tự động gửi báo cáo lúc 8:00 sáng và 8:00 tối (GMT+7) mỗi ngày."
    )


async def funding_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Đang fetch dữ liệu, chờ tôi một chút...")
    await run_and_send(context.bot, update.effective_chat.id)


async def run_and_send(bot, chat_id):
    try:
        deals = await fetch_funding_news()
        if not deals:
            await bot.send_message(chat_id=chat_id, text="❌ Không tìm thấy dữ liệu funding mới. Thử lại sau nhé.")
            return

        report = format_report(deals)

        # Telegram giới hạn 4096 ký tự mỗi tin — tự động chia nhỏ nếu cần
        chunk_size = 4000
        for i in range(0, len(report), chunk_size):
            chunk = report[i:i+chunk_size]
            await bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )

    except Exception as e:
        logger.error(f"Error in run_and_send: {e}")
        await bot.send_message(chat_id=chat_id, text=f"⚠️ Lỗi khi fetch dữ liệu: {str(e)}")


async def scheduled_job(bot):
    logger.info(f"Running scheduled job at {datetime.now(TIMEZONE)}")
    await run_and_send(bot, CHAT_ID)


async def post_init(application: Application):
    """Khởi động scheduler SAU KHI event loop đã chạy"""
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(scheduled_job, "cron", hour=8, minute=0, args=[application.bot])
    scheduler.add_job(scheduled_job, "cron", hour=20, minute=0, args=[application.bot])
    scheduler.start()
    logger.info("Scheduler started: 08:00 and 20:00 GMT+7")


def main():
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError("Thiếu BOT_TOKEN hoặc CHAT_ID trong environment variables!")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Register commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("funding", funding_command))

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
