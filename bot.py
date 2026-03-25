import os
import asyncio
import logging
import importlib.util

from routeros_api import RouterOsApiPool
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.request import HTTPXRequest

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]

_raw_ids = os.environ.get("ALLOWED_CHAT_ID", "")
ALLOWED_CHAT_IDS = {
    int(x.strip())
    for x in _raw_ids.split(",")
    if x.strip()
}

if not ALLOWED_CHAT_IDS:
    raise RuntimeError("ALLOWED_CHAT_ID is empty. Set: ALLOWED_CHAT_ID=id1,id2,...")

MT_HOST = os.environ["MT_HOST"]
MT_PORT = int(os.environ.get("MT_PORT", "8728"))
MT_USER = os.environ["MT_USER"]
MT_PASS = os.environ["MT_PASS"]

SCRIPT_ON = os.environ.get("SCRIPT_ON", "inet_on_250")
SCRIPT_OFF = os.environ.get("SCRIPT_OFF", "inet_off_250")

CUT_NAT_INDEX = int(os.environ.get("CUT_NAT_INDEX", "2"))

ALISA_NAME = os.environ.get("ALISA_NAME", "алиса")

PROXY = os.environ.get("PROXY", "")


def _ros_connect():
    pool = RouterOsApiPool(
        MT_HOST,
        username=MT_USER,
        password=MT_PASS,
        port=MT_PORT,
        use_ssl=(MT_PORT == 8729),
        plaintext_login=True,
    )
    return pool, pool.get_api()


def _ros_run_script(script_name: str) -> None:
    pool, api = _ros_connect()
    try:
        scripts = api.get_resource("/system/script")
        scripts.call("run", {"number": script_name})
    finally:
        pool.disconnect()


def _ros_get_inet_allowed_by_nat_index() -> bool:
    pool, api = _ros_connect()
    try:
        nat = api.get_resource("/ip/firewall/nat")
        rules = nat.get()

        if CUT_NAT_INDEX < 0 or CUT_NAT_INDEX >= len(rules):
            raise RuntimeError(
                f"NAT rules count={len(rules)}, index={CUT_NAT_INDEX} out of range"
            )

        rule = rules[CUT_NAT_INDEX]
        disabled_val = str(rule.get("disabled", "")).lower().strip()
        return disabled_val in ("yes", "true")
    finally:
        pool.disconnect()


async def ros_run_script(script_name: str) -> None:
    await asyncio.to_thread(_ros_run_script, script_name)


async def ros_get_status_text() -> str:
    inet_allowed = await asyncio.to_thread(_ros_get_inet_allowed_by_nat_index)
    if inet_allowed:
        return f"{ALISA_NAME} подключена к интернету"
    return f"{ALISA_NAME} не подключена к интернету"


def kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Статус", callback_data="status")],
        [
            InlineKeyboardButton("ВКЛ интернет", callback_data="on"),
            InlineKeyboardButton("ВЫКЛ интернет", callback_data="off"),
        ],
    ])


def _allowed_chat_id(chat_id) -> bool:
    return chat_id is not None and int(chat_id) in ALLOWED_CHAT_IDS


def allowed(update: Update) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.id in ALLOWED_CHAT_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.info("Incoming chat_id: %s, allowed: %s", update.effective_chat.id, allowed(update))
    if not allowed(update):
        return
    await update.message.reply_text("Панель:", reply_markup=kb())


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()

    if q.message is None or not _allowed_chat_id(q.message.chat_id):
        return

    try:
        if q.data == "on":
            await ros_run_script(SCRIPT_ON)
            await q.message.reply_text(await ros_get_status_text(), reply_markup=kb())

        elif q.data == "off":
            await ros_run_script(SCRIPT_OFF)
            await q.message.reply_text(await ros_get_status_text(), reply_markup=kb())

        elif q.data == "status":
            await q.message.reply_text(await ros_get_status_text(), reply_markup=kb())

        else:
            await q.message.reply_text("Неизвестная команда", reply_markup=kb())

    except Exception as e:
        logging.exception("MikroTik call failed")
        await q.message.reply_text(f"Ошибка: {type(e).__name__}: {e}", reply_markup=kb())


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.exception("Unhandled error", exc_info=context.error)


def main() -> None:
    logging.info("PROXY value: '%s'", PROXY)
    logging.info("socksio installed: %s", importlib.util.find_spec("socksio") is not None)
    logging.info("ALLOWED_CHAT_IDS: %s", ALLOWED_CHAT_IDS)

    builder = Application.builder().token(BOT_TOKEN)

    if PROXY:
        logging.info("Using proxy: %s", PROXY)
        request = HTTPXRequest(proxy=PROXY)
        builder = builder.request(request)

    app = builder.build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_error_handler(on_error)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
