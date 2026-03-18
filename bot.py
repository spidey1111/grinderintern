import os
import logging
import json
from datetime import datetime
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from scraper import fetch_funding_news, fetch_project_analysis
from formatter import format_header, format_single_deal_text, format_analysis_response

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache deals
_deals_cache: list[dict] = []


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Boring Grinder Funding Bot\n\n"
        "/funding — Fetch funding news ngay bay gio\n"
        "/help — Huong dan su dung\n\n"
        "Bot tu dong gui bao cao luc 8:00 sang va 8:00 toi GMT+7."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Lenh co the dung:\n\n"
        "/funding — Lay danh sach funding moi nhat\n\n"
        "Bam 'Click de xem them' duoi moi du an de doc phan tich chi tiet."
    )


async def funding_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Dang fetch du lieu, cho mot chut...")
    await run_and_send(context.bot, update.effective_chat.id)


async def run_and_send(bot, chat_id):
    global _deals_cache
    try:
        deals = await fetch_funding_news()
        if not deals:
            await bot.send_message(chat_id=chat_id, text="Khong tim thay du lieu funding moi. Thu lai sau.")
            return

        _deals_cache = deals

        # Gửi header
        header = format_header(deals)
        await bot.send_message(chat_id=chat_id, text=header, parse_mode="Markdown")

        # Gửi từng dự án kèm nút
        for idx, deal in enumerate(deals):
            text = format_single_deal_text(idx + 1, deal)
            if len(text) > 4000:
                text = text[:3990] + "..."

            keyboard = [[InlineKeyboardButton(
                "Click de xem them",
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
        logger.error(f"Error in run_and_send: {e}", exc_info=True)
        await bot.send_message(chat_id=chat_id, text=f"Loi: {str(e)}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        data = json.loads(query.data)
        if data.get("action") == "analysis":
            idx = data.get("idx", 0)
            if idx >= len(_deals_cache):
                await query.message.reply_text("Du lieu het han. Dung /funding de fetch lai.")
                return

            deal = _deals_cache[idx]
            await query.message.reply_text("Dang phan tich du an, cho 10-30 giay...")

            # Fetch and analyze
            raw_text = await fetch_project_analysis(
                project_code=deal.get("project_code", ""),
                name=deal.get("name", ""),
                website=deal.get("website", ""),
                twitter=deal.get("twitter", "")
            )

            analysis = format_analysis_response(deal, raw_text)

            # Split if too long
            chunk_size = 4000
            for i in range(0, len(analysis), chunk_size):
                await query.message.reply_text(
                    analysis[i:i+chunk_size],
                    disable_web_page_preview=True
                )

    except Exception as e:
        logger.error(f"Button callback error: {e}", exc_info=True)
        await query.message.reply_text(f"Loi: {str(e)}")


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
        raise ValueError("Thieu BOT_TOKEN hoac CHAT_ID!")

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
