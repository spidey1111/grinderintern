import os
import logging
import asyncio
from datetime import datetime
import pytz
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from scraper import fetch_funding_news
from formatter import format_report, format_farm_checklist

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache deals để dùng cho inline button
_deals_cache: list[dict] = []


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Boring Grinder Funding Bot*\n\n"
        "/funding — Fetch funding news ngay bây giờ\n"
        "/help — Hướng dẫn sử dụng\n\n"
        "Bot tự động gửi báo cáo lúc 8:00 sáng và 8:00 tối GMT+7.",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Hướng dẫn:*\n\n"
        "/funding — Lấy danh sách funding mới nhất\n\n"
        "Sau khi có report, bấm nút *📋 Checklist farm* dưới mỗi dự án để xem hành động cụ thể.",
        parse_mode="Markdown"
    )


async def funding_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Đang fetch dữ liệu, chờ tôi một chút...")
    await run_and_send(context.bot, update.effective_chat.id)


async def run_and_send(bot, chat_id):
    global _deals_cache
    try:
        deals = await fetch_funding_news()
        if not deals:
            await bot.send_message(chat_id=chat_id, text="❌ Không tìm thấy dữ liệu funding mới. Thử lại sau nhé.")
            return

        _deals_cache = deals

        # Gửi header report
        report = format_report(deals)
        chunk_size = 4000
        for i in range(0, len(report), chunk_size):
            await bot.send_message(
                chat_id=chat_id,
                text=report[i:i+chunk_size],
                parse_mode="Markdown",
                disable_web_page_preview=True
            )

        # Gửi inline buttons cho từng dự án
        for idx, deal in enumerate(deals):
            name = deal.get("name", f"Dự án {idx+1}")
            priority = "🔴" if "High" in str(deal.get("_priority", "")) else ""
            keyboard = [[InlineKeyboardButton(
                f"📋 Checklist farm — {name}",
                callback_data=json.dumps({"action": "farm", "idx": idx})
            )]]
            await bot.send_message(
                chat_id=chat_id,
                text=f"_{name}_",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Error in run_and_send: {e}")
        await bot.send_message(chat_id=chat_id, text=f"⚠️ Lỗi: {str(e)}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        data = json.loads(query.data)
        if data.get("action") == "farm":
            idx = data.get("idx", 0)
            if idx < len(_deals_cache):
                deal = _deals_cache[idx]
                checklist = format_farm_checklist(deal)
                await query.message.reply_text(
                    checklist,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
            else:
                await query.message.reply_text("⚠️ Dữ liệu đã hết hạn. Dùng /funding để fetch lại nhé.")
    except Exception as e:
        logger.error(f"Button callback error: {e}")
        await query.message.reply_text(f"⚠️ Lỗi: {str(e)}")


async def scheduled_job(bot):
    logger.info(f"Scheduled job at {datetime.now(TIMEZONE)}")
    await run_and_send(bot, CHAT_ID)


async def post_init(application: Application):
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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("funding", funding_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
