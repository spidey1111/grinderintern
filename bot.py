import os
import logging
import json
from datetime import datetime
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from scraper import fetch_funding_news, fetch_project_page_content
from formatter import format_header, format_single_deal_text, format_analysis_text

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_deals_cache: list[dict] = []


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Boring Grinder Funding Bot\n\n"
        "/funding — Fetch danh sách funding mới nhất\n"
        "/help — Hướng dẫn sử dụng\n\n"
        "Bot tự động gửi báo cáo lúc 8:00 sáng và 8:00 tối GMT+7."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Lệnh có thể dùng:\n\n"
        "/funding — Lấy danh sách funding mới nhất\n\n"
        "Bấm 'Click để xem thêm' dưới mỗi dự án để đọc phân tích chi tiết."
    )


async def funding_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Đang fetch dữ liệu, chờ một chút...")
    await run_and_send(context.bot, update.effective_chat.id)


async def run_and_send(bot, chat_id):
    global _deals_cache
    try:
        deals = await fetch_funding_news()
        if not deals:
            await bot.send_message(chat_id=chat_id, text="Không tìm thấy dữ liệu funding mới. Thử lại sau nhé.")
            return

        _deals_cache = deals

        # Header
        await bot.send_message(
            chat_id=chat_id,
            text=format_header(deals),
            parse_mode="Markdown"
        )

        # Từng dự án
        for idx, deal in enumerate(deals):
            text = format_single_deal_text(idx + 1, deal)
            if len(text) > 4000:
                text = text[:3990] + "..."

            keyboard = [[InlineKeyboardButton(
                "Click để xem thêm",
                callback_data=json.dumps({"action": "analysis", "idx": idx})
            )]]
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
                disable_web_page_preview=True
            )

    except Exception as e:
        logger.error(f"run_and_send error: {e}", exc_info=True)
        await bot.send_message(chat_id=chat_id, text=f"Lỗi: {str(e)}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        data = json.loads(query.data)
        if data.get("action") != "analysis":
            return

        idx = data.get("idx", 0)
        if idx >= len(_deals_cache):
            await query.message.reply_text("Dữ liệu đã hết hạn. Dùng /funding để fetch lại nhé.")
            return

        deal = _deals_cache[idx]
        await query.message.reply_text("Đang tải nội dung từ nguồn chính thức, chờ một chút...")

        raw_content = await fetch_project_page_content(
            website=deal.get("website", ""),
            twitter=deal.get("twitter", ""),
            name=deal.get("name", "")
        )

        analysis = format_analysis_text(deal, raw_content)

        # Chia nhỏ nếu dài
        chunk_size = 4000
        for i in range(0, len(analysis), chunk_size):
            await query.message.reply_text(
                analysis[i:i+chunk_size],
                disable_web_page_preview=True
            )

    except Exception as e:
        logger.error(f"Button callback error: {e}", exc_info=True)
        await query.message.reply_text(f"Lỗi: {str(e)}")


async def scheduled_job(bot):
    logger.info(f"Scheduled job at {datetime.now(TIMEZONE)}")
    await run_and_send(bot, CHAT_ID)


async def post_init(application: Application):
    # Scheduler tạm tắt — bật lại bằng cách uncomment 4 dòng dưới
    # scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    # scheduler.add_job(scheduled_job, "cron", hour=8, minute=0, args=[application.bot])
    # scheduler.add_job(scheduled_job, "cron", hour=20, minute=0, args=[application.bot])
    # scheduler.start()
    logger.info("Scheduler đang tắt. Dùng /funding để fetch thủ công.")


def main():
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError("Thiếu BOT_TOKEN hoặc CHAT_ID!")

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
