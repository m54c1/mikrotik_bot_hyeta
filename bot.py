import os
import asyncio
import logging

from routeros_api import RouterOsApiPool
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ALLOWED_CHAT_ID = int(os.environ["ALLOWED_CHAT_ID"])

MT_HOST = os.environ["MT_HOST"]
MT_PORT = int(os.environ.get("MT_PORT", "8728"))
MT_USER = os.environ["MT_USER"]
MT_PASS = os.environ["MT_PASS"]

SCRIPT_ON = os.environ.get("SCRIPT_ON", "inet_on_250")
SCRIPT_OFF = os.environ.get("SCRIPT_OFF", "inet_off_250")
SCRIPT_STATUS = os.environ.get("SCRIPT_STATUS", "inet_status_250")

ALISA_NAME = os.environ.get("ALISA_NAME", "алиса")


def _ros_run_script_ret(script_name: str) -> str:
    api_pool = RouterOsApiPool(
        MT_HOST,
        username=MT_USER,
        password=MT_PASS,
        port=MT_PORT,
        use_ssl=(MT_PORT == 8729),
        plaintext_login=True,
    )
    api = api_pool.get_api()

    # ВАЖНО: binary_resource + system/script/run, чтобы получить done_message['ret'] [web:103][web:59]
    resp = api.get_binary_resource("/").call(
        "system/script/run",
        {"number": script_name.encode("utf-8")},
    )

    api_pool.disconnect()

    ret = ""
    if hasattr(resp, "done_message") and isinstance(resp.done_message, dict):
        ret = resp.done_message.get("ret", b"")

    if isinstance(ret, (bytes, bytearray)):
        ret = ret.decode("utf-8", errors="ignore")

    return (ret or "").strip()


async def ros_run_script_ret(script_name: str) -> str:
    return await asyncio.to_thread(_ros_run_script_ret, script_name)


def status_to_text(raw: str) -> str:
    s = (raw or "").strip().upper()
    if s == "ON":
        return f"{ALISA_NAME} подключена к интернету"
    if s == "OFF":
        return f"{ALISA_NAME} не подключена к интернету"
    return f"{ALISA_NAME}: статус непонятен (ответ: {raw!r})"


def kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Статус", callback_data="status")],
        [
            InlineKeyboardButton("ВКЛ интернет", callback_data="on"),
            InlineKeyboardButton("ВЫКЛ интернет", callback_data="off"),
        ],
    ])


def allowed(update: Update) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.id == ALLOWED_CHAT_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        return
    await update.message.reply_text("Панель:", reply_markup=kb())


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()

    if q.message is None or q.message.chat_id != ALLOWED_CHAT_ID:
        return

    try:
        if q.data == "on":
            await ros_run_script_ret(SCRIPT_ON)
            raw = await ros_run_script_ret(SCRIPT_STATUS)
            await q.message.reply_text(status_to_text(raw), reply_markup=kb())

        elif q.data == "off":
            await ros_run_script_ret(SCRIPT_OFF)
            raw = await ros_run_script_ret(SCRIPT_STATUS)
            await q.message.reply_text(status_to_text(raw), reply_markup=kb())

        elif q.data == "status":
            raw = await ros_run_script_ret(SCRIPT_STATUS)
            await q.message.reply_text(status_to_text(raw), reply_markup=kb())

        else:
            await q.message.reply_text("Неизвестная команда", reply_markup=kb())

    except Exception as e:
        logging.exception("MikroTik call failed")
        await q.message.reply_text(f"Ошибка: {type(e).__name__}: {e}", reply_markup=kb())


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.exception("Unhandled error", exc_info=context.error)


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_error_handler(on_error)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

