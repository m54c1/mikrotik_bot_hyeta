import os
import asyncio
import logging

from routeros_api import RouterOsApiPool
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ALLOWED_CHAT_IDS = {
    int(x.strip())
    for x in os.environ["ALLOWED_CHAT_ID"].split(",")
    if x.strip()
}

MT_HOST = os.environ["MT_HOST"]
MT_PORT = int(os.environ.get("MT_PORT", "8728"))
MT_USER = os.environ["MT_USER"]
MT_PASS = os.environ["MT_PASS"]

# Скрипты на MikroTik (они включают/выключают CUT и чистят conntrack)
SCRIPT_ON = os.environ.get("SCRIPT_ON", "inet_on_250")
SCRIPT_OFF = os.environ.get("SCRIPT_OFF", "inet_off_250")

# "номер" правила в NAT: 2 == третий (если считать с 0)
CUT_NAT_INDEX = int(os.environ.get("CUT_NAT_INDEX", "2"))

ALISA_NAME = os.environ.get("ALISA_NAME", "алиса")


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
        # у тебя работает запуск через number=имя_скрипта
        scripts.call("run", {"number": script_name})
    finally:
        pool.disconnect()


def _ros_get_inet_allowed_by_nat_index() -> bool:
    """
    True  -> алиса подключена к интернету
    False -> алиса не подключена к интернету

    Логика:
    - CUT правило (action=accept в srcnat) когда ВКЛЮЧЕНО (disabled=no) => интернет РЕЖЕТСЯ
    - когда ВЫКЛЮЧЕНО (disabled=yes) => интернет ЕСТЬ
    """
    pool, api = _ros_connect()
    try:
        nat = api.get_resource("/ip/firewall/nat")
        rules = nat.get()  # список правил NAT [web:61]

        if CUT_NAT_INDEX < 0 or CUT_NAT_INDEX >= len(rules):
            raise RuntimeError(
                f"NAT rules count={len(rules)}, index={CUT_NAT_INDEX} out of range"
            )

        rule = rules[CUT_NAT_INDEX]
        disabled_val = str(rule.get("disabled", "")).lower().strip()

        cut_rule_disabled = disabled_val in ("yes", "true")
        return cut_rule_disabled  # True => интернет есть
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


def allowed(update: Update) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.id in ALLOWED_CHAT_IDS


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
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_error_handler(on_error)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

