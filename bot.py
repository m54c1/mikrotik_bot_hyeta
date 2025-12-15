import os
import asyncio
import logging

from routeros_api import RouterOsApiPool
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID"))

MT_HOST = os.getenv("MT_HOST")
MT_PORT = int(os.getenv("MT_PORT", "8728"))
MT_USER = os.getenv("MT_USER")
MT_PASS = os.getenv("MT_PASS")

SCRIPT_ON = os.getenv("SCRIPT_ON", "inet_on_250")
SCRIPT_OFF = os.getenv("SCRIPT_OFF", "inet_off_250")
SCRIPT_STATUS = os.getenv("SCRIPT_STATUS", "inet_status_250")


def _ros_run_script(script_name: str) -> str:
    api_pool = RouterOsApiPool(
        MT_HOST,
        username=MT_USER,
        password=MT_PASS,
        port=MT_PORT,
        use_ssl=(MT_PORT == 8729),
        plaintext_login=True,
    )
    api = api_pool.get_api()

    run_res = api.get_resource('/system/script/run')
    run_res.call('run', {'number': script_name})

    api_pool.disconnect()
    return script_name


async def ros_run_script(script_name: str) -> str:
    return await asyncio.to_thread(_ros_run_script, script_name)


def kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Статус", callback_data="status")],
        [
            InlineKeyboardButton("ВКЛ интернет", callback_data="on"),
            InlineKeyboardButton("ВЫКЛ интернет", callback_data="off"),
        ],
    ])


def _allowed(update: Update) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.id == ALLOWED_CHAT_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    await update.message.reply_text("Панель управления:", reply_markup=kb())


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()

    if q.message is None or q.message.chat_id != ALLOWED_CHAT_ID:
        return

    if q.data == "on":
        res = await ros_run_script(SCRIPT_ON)
        await q.message.reply_text(f"ОК: {res}", reply_markup=kb())
    elif q.data == "off":
        res = await ros_run_script(SCRIPT_OFF)
        await q.message.reply_text(f"ОК: {res}", reply_markup=kb())
    elif q.data == "status":
        res = await ros_run_script(SCRIPT_STATUS)
        await q.message.reply_text(f"ОК: {res}", reply_markup=kb())
    else:
        await q.message.reply_text("Неизвестная команда", reply_markup=kb())


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

