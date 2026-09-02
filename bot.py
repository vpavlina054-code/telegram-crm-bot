# ============================================
# Telegram CRM Bot
# Version: 2.0
# ============================================

import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
import gspread
from google.oauth2.service_account import Credentials

TOKEN = os.environ.get("BOT_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
PRIHODI_SPREADSHEET_ID = os.environ.get("PRIHODI_SPREADSHEET_ID")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS")

AMOUNT, SOURCE, REASON, TRANSFER_FROM, TRANSFER_TO = range(5)

COL = {
    "TELEGRAM_ID": 12,
    "BANKI": 13,
    "KASA": 14,
    "ALLPAY": 15,
    "PAY": 16,
    "BALANCE": 17,
    "RAZHODI": 18,
    "PRIHODI": 19,
    "TRANSFERI": 20,
    "PAYNOW": 21,
    "NOTIFY": 22,
    "NOTIFY_TRANSFER": 23,
}

_client = None


def get_client():
    global _client
    if _client is None:
        creds_dict = json.loads(GOOGLE_CREDENTIALS)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        _client = gspread.authorize(creds)
    return _client


def find_user_by_telegram_id(telegram_id):
    data = get_client().open_by_key(SPREADSHEET_ID).worksheet("SYSTEM_USERS").get_all_values()
    for row in data[1:]:
        if len(row) > COL["TELEGRAM_ID"] and str(row[COL["TELEGRAM_ID"]]).strip() == str(telegram_id):
            return {"user": row[0], "row": row}
    return None


def find_user_row_by_name(name):
    data = get_client().open_by_key(SPREADSHEET_ID).worksheet("SYSTEM_USERS").get_all_values()
    for row in data[1:]:
        if row and row[0].strip() == str(name).strip():
            return row
    return None


def has_permission(user_row, column_index):
    if user_row and len(user_row) > column_index:
        return str(user_row[column_index]).strip().upper() == "DA"
    return False


async def require_user(update, column_index=None):
    user = find_user_by_telegram_id(update.effective_user.id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return None
    if column_index is not None and not has_permission(user["row"], column_index):
        await update.message.reply_text("Нямаш права за тази информация")
        return None
    return user


def get_current_datetime():
    return datetime.now(ZoneInfo("Europe/Sofia")).strftime("%d.%m.%Y %H:%M")


def parse_amount(text):
    if not text:
        return 0.0
    cleaned = str(text).replace("€", "").replace(" ", "").replace(",", "")
    try:
        return float(cleaned)
    except:
        return 0.0


def get_unique_list_from_column(sheet_name, column_index):
    data = get_client().open_by_key(PRIHODI_SPREADSHEET_ID).worksheet(sheet_name).get_all_values()
    values = set()
    for row in data[1:]:
        if len(row) > column_index and row[column_index].strip():
            values.add(row[column_index].strip())
    return sorted(list(values))


def get_system_users():
    data = get_client().open_by_key(SPREADSHEET_ID).worksheet("SYSTEM_USERS").get_all_values()
    return [row[0].strip() for row in data[1:] if row and row[0].strip()]


def get_user_balance(username):
    data = get_client().open_by_key(PRIHODI_SPREADSHEET_ID).worksheet("Total").get_all_values()
    for row in data:
        if len(row) > 2 and row[1].strip() == username:
            return row[2].strip()
    return "—"


def get_all_balances():
    try:
        data = get_client().open_by_key(PRIHODI_SPREADSHEET_ID).worksheet("Total").get_all_values()
        balances = []
        skip = {"КАСИЕР / ПОТРЕБИТЕЛ", "КАСИЕР", "ПОТРЕБИТЕЛ", "USER"}
        for row in data:
            if len(row) > 2 and row[1].strip() and row[2].strip():
                name = row[1].strip()
                if name.upper() in skip:
                    continue
                balances.append(f"{name}: {row[2].strip()}")
        return "\n".join(balances) if balances else "Няма данни"
    except Exception as e:
        return f"Грешка при четене на наличности: {e}"


async def send_to_telegram_id(context, telegram_id, text):
    if telegram_id and str(telegram_id).isdigit():
        try:
            await context.bot.send_message(chat_id=int(telegram_id), text=text)
        except:
            pass


async def send_notifications(context, base_message):
    try:
        full_message = f"{base_message}\n\nТекущи наличности:\n{get_all_balances()}"
        data = get_client().open_by_key(SPREADSHEET_ID).worksheet("SYSTEM_USERS").get_all_values()
        for row in data[1:]:
            if has_permission(row, COL["NOTIFY"]):
                telegram_id = row[COL["TELEGRAM_ID"]].strip() if len(row) > COL["TELEGRAM_ID"] else ""
                await send_to_telegram_id(context, telegram_id, full_message)
    except Exception as e:
        print(f"Грешка при известия: {e}")


async def send_transfer_personal_notifications(context, from_user, to_user, amount, reason):
    from_row = find_user_row_by_name(from_user)
    to_row = find_user_row_by_name(to_user)

    if has_permission(from_row, COL["NOTIFY_TRANSFER"]):
        from_balance = get_user_balance(from_user)
        text = (
            f"📤 Изпратен трансфер\n"
            f"Към: {to_user}\n"
            f"Сума: {amount} €\n"
            f"Основание: {reason if reason else '—'}\n\n"
            f"Твоята каса сега: {from_balance}"
        )
        telegram_id = from_row[COL["TELEGRAM_ID"]].strip() if from_row and len(from_row) > COL["TELEGRAM_ID"] else ""
        await send_to_telegram_id(context, telegram_id, text)

    if has_permission(to_row, COL["NOTIFY_TRANSFER"]) and from_user != to_user:
        to_balance = get_user_balance(to_user)
        text = (
            f"📥 Получен трансфер\n"
            f"От: {from_user}\n"
            f"Сума: {amount} €\n"
            f"Основание: {reason if reason else '—'}\n\n"
            f"Твоята каса сега: {to_balance}"
        )
        telegram_id = to_row[COL["TELEGRAM_ID"]].strip() if to_row and len(to_row) > COL["TELEGRAM_ID"] else ""
        await send_to_telegram_id(context, telegram_id, text)


def pack_keyboard(buttons, per_row=2, extra_rows=None):
    keyboard = []
    row = []
    for btn in buttons:
        row.append(btn)
        if len(row) == per_row:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    if extra_rows:
        keyboard.extend(extra_rows)
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_main_keyboard(user_row):
    buttons = []
    if has_permission(user_row, COL["BANKI"]):
        buttons.append(KeyboardButton("Банки"))
    if has_permission(user_row, COL["KASA"]):
        buttons.append(KeyboardButton("Наличност"))
    if has_permission(user_row, COL["ALLPAY"]):
        buttons.append(KeyboardButton("Всички задължения"))
    if has_permission(user_row, COL["PAY"]):
        buttons.append(KeyboardButton("Задължения"))
    if has_permission(user_row, COL["BALANCE"]):
        buttons.append(KeyboardButton("Моя Баланс"))
    if has_permission(user_row, COL["PRIHODI"]) or has_permission(user_row, COL["RAZHODI"]) or has_permission(user_row, COL["TRANSFERI"]):
        buttons.append(KeyboardButton("Дневни операции"))
    if has_permission(user_row, COL["PAYNOW"]):
        buttons.append(KeyboardButton("Операция"))
    return pack_keyboard(buttons)


def get_daily_keyboard(user_row):
    buttons = []
    if has_permission(user_row, COL["PRIHODI"]):
        buttons.append(KeyboardButton("Приходи"))
    if has_permission(user_row, COL["RAZHODI"]):
        buttons.append(KeyboardButton("Разходи"))
    if has_permission(user_row, COL["TRANSFERI"]):
        buttons.append(KeyboardButton("Трансфери"))
    return pack_keyboard(buttons, extra_rows=[[KeyboardButton("← Назад")]])


def get_operation_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Приход"), KeyboardButton("Разход")],
        [KeyboardButton("Трансфер")],
        [KeyboardButton("← Назад")]
    ], resize_keyboard=True)


def get_list_keyboard(items):
    return pack_keyboard([KeyboardButton(item) for item in items], extra_rows=[[KeyboardButton("← Отказ")]])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Този бот не работи")


async def da(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update)
    if user is None:
        return
    await update.message.reply_text(
        f"Здравей, {user['user']}!\nИзбери опция:",
        reply_markup=get_main_keyboard(user["row"])
    )


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update)
    if user is None:
        return
    await update.message.reply_text("Главно меню:", reply_markup=get_main_keyboard(user["row"]))


async def daily_operations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update)
    if user is None:
        return
    await update.message.reply_text("Избери тип операция:", reply_markup=get_daily_keyboard(user["row"]))


async def operation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update, COL["PAYNOW"])
    if user is None:
        return
    await update.message.reply_text("Избери тип операция:", reply_markup=get_operation_keyboard())


async def banks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update, COL["BANKI"])
    if user is None:
        return
    try:
        data = get_client().open_by_key(SPREADSHEET_ID).worksheet("LiveStatus").get_all_values()
        update_info = data[1][0] if len(data) > 1 else "Няма данни"
        start_idx = total_idx = None
        for i, row in enumerate(data):
            if row and "БАНКОВИ НАЛИЧНОСТИ" in str(row[0]).upper():
                start_idx = i
            if row and "ОБЩО БАНКИ" in str(row[0]).upper():
                total_idx = i
                break
        if start_idx is None or total_idx is None:
            await update.message.reply_text("Не мога да намеря секцията с банките")
            return
        firms = []
        for i in range(start_idx + 2, total_idx):
            row = data[i]
            if len(row) >= 3 and row[0].strip():
                firms.append((row[0].strip(), row[1].strip() if len(row) > 1 else "", row[2].strip() if len(row) > 2 else ""))
        total_sum = data[total_idx][2].strip() if len(data[total_idx]) > 2 else "—"
        message = f"<b>{update_info}</b>\n\n<b>БАНКОВИ НАЛИЧНОСТИ</b>\n\n"
        for firm, date, balance in firms:
            message += f"<b>{firm}</b>\n{date}  |  {balance}\n\n"
        message += f"────────────────\n<b>ОБЩО БАНКИ:</b> {total_sum}"
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_main_keyboard(user["row"]))
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")


async def nаличност(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update, COL["KASA"])
    if user is None:
        return
    try:
        data = get_client().open_by_key(SPREADSHEET_ID).worksheet("LiveStatus").get_all_values()
        update_info = data[1][0] if len(data) > 1 else "Няма данни"
        start_idx = end_idx = None
        for i, row in enumerate(data):
            if row and "КАСА И НЕРАЗПРЕДЕЛЕНИ" in str(row[0]).upper():
                start_idx = i
            if row and "ЗАДЪЛЖЕНИЯ КЪМ ОБЕКТИ" in str(row[0]).upper():
                end_idx = i
                break
        if start_idx is None or end_idx is None:
            await update.message.reply_text("Не мога да намеря секцията")
            return
        items = []
        for i in range(start_idx + 1, end_idx):
            row = data[i]
            if row and row[0].strip():
                value = row[2].strip() if len(row) > 2 else ""
                if value:
                    items.append((row[0].strip(), value))
        message = f"<b>{update_info}</b>\n\n<b>КАСА И НЕРАЗПРЕДЕЛЕНИ</b>\n\n"
        for label, value in items:
            message += f"{label}\n<b>{value}</b>\n\n"
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_main_keyboard(user["row"]))
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")


async def allpay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update, COL["ALLPAY"])
    if user is None:
        return
    try:
        data = get_client().open_by_key(SPREADSHEET_ID).worksheet("LiveStatus").get_all_values()
        update_info = data[1][0] if len(data) > 1 else "Няма данни"
        start_idx = total_idx = None
        for i, row in enumerate(data):
            if row and "ЗАДЪЛЖЕНИЯ КЪМ ОБЕКТИ" in str(row[0]).upper():
                start_idx = i
            if row and "ОБЩО ЗАДЪЛЖЕНИЯ" in str(row[0]).upper():
                total_idx = i
                break
        if start_idx is None or total_idx is None:
            await update.message.reply_text("Не мога да намеря секцията")
            return
        items = []
        for i in range(start_idx + 2, total_idx):
            row = data[i]
            if row and row[0].strip():
                items.append((
                    row[0].strip(),
                    row[1].strip() if len(row) > 1 else "",
                    row[2].strip() if len(row) > 2 else "",
                    row[3].strip() if len(row) > 3 else "",
                    row[4].strip() if len(row) > 4 else ""
                ))
        total_row = data[total_idx]
        message = f"<b>{update_info}</b>\n\n<b>ЗАДЪЛЖЕНИЯ КЪМ ОБЕКТИ</b>\n\n"
        for name, date, total_debt, plan, required in items:
            message += f"<b>{name}</b>\n{date} | {total_debt} | {plan} | {required}\n\n"
        message += f"────────────────\n<b>ОБЩО ЗАДЪЛЖЕНИЯ:</b>\nОбщо дълг: {total_row[2] if len(total_row) > 2 else '—'}\nИзискуемо: {total_row[4] if len(total_row) > 4 else '—'}"
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_main_keyboard(user["row"]))
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")


async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update, COL["PAY"])
    if user is None:
        return
    try:
        data = get_client().open_by_key(SPREADSHEET_ID).worksheet("LiveStatus").get_all_values()
        update_info = data[1][0] if len(data) > 1 else "Няма данни"
        start_idx = total_idx = None
        for i, row in enumerate(data):
            if row and "ЗАДЪЛЖЕНИЯ КЪМ ОБЕКТИ" in str(row[0]).upper():
                start_idx = i
            if row and "ОБЩО ЗАДЪЛЖЕНИЯ" in str(row[0]).upper():
                total_idx = i
                break
        if start_idx is None or total_idx is None:
            await update.message.reply_text("Не мога да намеря секцията")
            return
        items = []
        for i in range(start_idx + 2, total_idx):
            row = data[i]
            if row and row[0].strip():
                required = row[4].strip() if len(row) > 4 else ""
                items.append((row[0].strip(), required, parse_amount(required)))
        items.sort(key=lambda x: x[2], reverse=True)
        message = f"<b>{update_info}</b>\n\n<b>ИЗИСКУЕМИ СУМИ</b>\n\n"
        for name, required, _ in items:
            message += f"<b>{name}</b>\n{required}\n\n"
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_main_keyboard(user["row"]))
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")


async def my_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update, COL["BALANCE"])
    if user is None:
        return
    try:
        balance = get_user_balance(user["user"])
        if balance == "—":
            await update.message.reply_text(f"Не намерих наличност за {user['user']}")
            return
        message = f"Твоята текуща наличност:\n\n<b>{user['user']}</b>\n<b>{balance}</b>"
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_main_keyboard(user["row"]))
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")


async def show_prihodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update, COL["PRIHODI"])
    if user is None:
        return
    try:
        data = get_client().open_by_key(PRIHODI_SPREADSHEET_ID).worksheet("Prihodi").get_all_values()
        records = [row for row in data[1:] if row and row[0].strip()][-10:]
        records.reverse()
        message = "<b>Последни 10 Прихода:</b>\n\n"
        for row in records:
            message += f"<b>{row[0]}</b>\n{row[1] if len(row)>1 else ''} €\n{row[2] if len(row)>2 else ''} → {row[4] if len(row)>4 else ''}\n{row[3] if len(row)>3 else ''}\n\n"
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_daily_keyboard(user["row"]))
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")


async def show_razhodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update, COL["RAZHODI"])
    if user is None:
        return
    try:
        data = get_client().open_by_key(PRIHODI_SPREADSHEET_ID).worksheet("Razhodi").get_all_values()
        records = [row for row in data[1:] if row and row[0].strip()][-10:]
        records.reverse()
        message = "<b>Последни 10 Разхода:</b>\n\n"
        for row in records:
            message += f"<b>{row[0]}</b>\n{row[1] if len(row)>1 else ''} €\n{row[2] if len(row)>2 else ''}\n{row[3] if len(row)>3 else ''}\nПлатил: {row[4] if len(row)>4 else ''}\n\n"
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_daily_keyboard(user["row"]))
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")


async def show_transfers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update, COL["TRANSFERI"])
    if user is None:
        return
    try:
        data = get_client().open_by_key(PRIHODI_SPREADSHEET_ID).worksheet("Transfers").get_all_values()
        records = [row for row in data[1:] if row and row[0].strip()][-10:]
        records.reverse()
        message = "<b>Последни 10 Трансфера:</b>\n\n"
        for row in records:
            message += f"<b>{row[0]}</b>\n{row[1] if len(row)>1 else ''} €\n{row[2] if len(row)>2 else ''} → {row[3] if len(row)>3 else ''}\n"
            if len(row) > 4 and row[4]:
                message += f"{row[4]}\n"
            message += "\n"
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_daily_keyboard(user["row"]))
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")


async def prihod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update, COL["PAYNOW"])
    if user is None:
        return ConversationHandler.END
    context.user_data.clear()
    context.user_data["user"] = user["user"]
    context.user_data["row"] = user["row"]
    await update.message.reply_text("Въведи сума за Приход:", reply_markup=ReplyKeyboardRemove())
    return AMOUNT


async def prihod_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", ".")
    try:
        context.user_data["amount"] = float(text)
    except:
        await update.message.reply_text("Моля, въведи валидно число:")
        return AMOUNT
    sources = get_unique_list_from_column("Prihodi", 2) or ["KASA", "Друг"]
    await update.message.reply_text("Избери от кого е приходът:", reply_markup=get_list_keyboard(sources))
    return SOURCE


async def prihod_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "← Отказ":
        await update.message.reply_text("Отказано.", reply_markup=get_main_keyboard(context.user_data.get("row", [])))
        return ConversationHandler.END
    context.user_data["source"] = text
    await update.message.reply_text("Напиши основание:", reply_markup=ReplyKeyboardRemove())
    return REASON


async def prihod_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    try:
        get_client().open_by_key(PRIHODI_SPREADSHEET_ID).worksheet("Prihodi").append_row([
            get_current_datetime(),
            context.user_data["amount"],
            context.user_data["source"],
            reason,
            context.user_data["user"]
        ])
        await update.message.reply_text(
            f"✅ Успешен Приход!\nСума: {context.user_data['amount']} €\nОт: {context.user_data['source']}\nОснование: {reason}",
            reply_markup=get_main_keyboard(context.user_data.get("row", []))
        )
        await send_notifications(context, (
            f"🔔 Нов Приход\n"
            f"Сума: {context.user_data['amount']} €\n"
            f"От: {context.user_data['source']}\n"
            f"Основание: {reason}\n"
            f"Приел: {context.user_data['user']}"
        ))
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}", reply_markup=get_main_keyboard(context.user_data.get("row", [])))
    return ConversationHandler.END


async def razhod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update, COL["PAYNOW"])
    if user is None:
        return ConversationHandler.END
    context.user_data.clear()
    context.user_data["user"] = user["user"]
    context.user_data["row"] = user["row"]
    await update.message.reply_text("Въведи сума за Разход:", reply_markup=ReplyKeyboardRemove())
    return AMOUNT


async def razhod_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", ".")
    try:
        context.user_data["amount"] = float(text)
    except:
        await update.message.reply_text("Моля, въведи валидно число:")
        return AMOUNT
    receivers = get_unique_list_from_column("Razhodi", 2) or ["Друг"]
    await update.message.reply_text("Избери получател:", reply_markup=get_list_keyboard(receivers))
    return SOURCE


async def razhod_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "← Отказ":
        await update.message.reply_text("Отказано.", reply_markup=get_main_keyboard(context.user_data.get("row", [])))
        return ConversationHandler.END
    context.user_data["source"] = text
    await update.message.reply_text("Напиши основание:", reply_markup=ReplyKeyboardRemove())
    return REASON


async def razhod_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    try:
        get_client().open_by_key(PRIHODI_SPREADSHEET_ID).worksheet("Razhodi").append_row([
            get_current_datetime(),
            context.user_data["amount"],
            context.user_data["source"],
            reason,
            context.user_data["user"]
        ])
        await update.message.reply_text(
            f"✅ Успешен Разход!\nСума: {context.user_data['amount']} €\nПолучател: {context.user_data['source']}\nОснование: {reason}",
            reply_markup=get_main_keyboard(context.user_data.get("row", []))
        )
        await send_notifications(context, (
            f"🔔 Нов Разход\n"
            f"Сума: {context.user_data['amount']} €\n"
            f"Получател: {context.user_data['source']}\n"
            f"Основание: {reason}\n"
            f"Платил: {context.user_data['user']}"
        ))
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}", reply_markup=get_main_keyboard(context.user_data.get("row", [])))
    return ConversationHandler.END


async def transfer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_user(update, COL["PAYNOW"])
    if user is None:
        return ConversationHandler.END
    context.user_data.clear()
    context.user_data["user"] = user["user"]
    context.user_data["row"] = user["row"]
    await update.message.reply_text("Въведи сума за Трансфер:", reply_markup=ReplyKeyboardRemove())
    return AMOUNT


async def transfer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", ".")
    try:
        context.user_data["amount"] = float(text)
    except:
        await update.message.reply_text("Моля, въведи валидно число:")
        return AMOUNT
    await update.message.reply_text("От кого (Изпращач):", reply_markup=get_list_keyboard(get_system_users()))
    return TRANSFER_FROM


async def transfer_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "← Отказ":
        await update.message.reply_text("Отказано.", reply_markup=get_main_keyboard(context.user_data.get("row", [])))
        return ConversationHandler.END
    context.user_data["from_user"] = text
    await update.message.reply_text("Към кого (Получател):", reply_markup=get_list_keyboard(get_system_users()))
    return TRANSFER_TO


async def transfer_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "← Отказ":
        await update.message.reply_text("Отказано.", reply_markup=get_main_keyboard(context.user_data.get("row", [])))
        return ConversationHandler.END
    context.user_data["to_user"] = text
    await update.message.reply_text("Основание (или - ако няма):", reply_markup=ReplyKeyboardRemove())
    return REASON


async def transfer_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    if reason == "-":
        reason = ""
    try:
        get_client().open_by_key(PRIHODI_SPREADSHEET_ID).worksheet("Transfers").append_row([
            get_current_datetime(),
            context.user_data["amount"],
            context.user_data["from_user"],
            context.user_data["to_user"],
            reason
        ])
        await update.message.reply_text(
            f"✅ Успешен Трансфер!\n{context.user_data['from_user']} → {context.user_data['to_user']}\nСума: {context.user_data['amount']} €",
            reply_markup=get_main_keyboard(context.user_data.get("row", []))
        )
        await send_notifications(context, (
            f"🔔 Нов Трансфер\n"
            f"Сума: {context.user_data['amount']} €\n"
            f"{context.user_data['from_user']} → {context.user_data['to_user']}\n"
            f"Основание: {reason if reason else '—'}"
        ))
        await send_transfer_personal_notifications(
            context,
            context.user_data["from_user"],
            context.user_data["to_user"],
            context.user_data["amount"],
            reason
        )
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}", reply_markup=get_main_keyboard(context.user_data.get("row", [])))
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операцията е отменена.", reply_markup=get_main_keyboard(context.user_data.get("row", [])))
    return ConversationHandler.END


def main():
    app = Application.builder().token(TOKEN).build()

    prihod_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Приход$"), prihod_start)],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, prihod_amount)],
            SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, prihod_source)],
            REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, prihod_reason)],
        },
        fallbacks=[MessageHandler(filters.Regex("^← Отказ$"), cancel)]
    )
    razhod_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Разход$"), razhod_start)],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, razhod_amount)],
            SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, razhod_source)],
            REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, razhod_reason)],
        },
        fallbacks=[MessageHandler(filters.Regex("^← Отказ$"), cancel)]
    )
    transfer_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Трансфер$"), transfer_start)],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_amount)],
            TRANSFER_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_from)],
            TRANSFER_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_to)],
            REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_reason)],
        },
        fallbacks=[MessageHandler(filters.Regex("^← Отказ$"), cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("da", da))
    app.add_handler(prihod_conv)
    app.add_handler(razhod_conv)
    app.add_handler(transfer_conv)
    app.add_handler(MessageHandler(filters.Regex("^Банки$"), banks))
    app.add_handler(MessageHandler(filters.Regex("^Наличност$"), nаличност))
    app.add_handler(MessageHandler(filters.Regex("^Всички задължения$"), allpay))
    app.add_handler(MessageHandler(filters.Regex("^Задължения$"), pay))
    app.add_handler(MessageHandler(filters.Regex("^Моя Баланс$"), my_balance))
    app.add_handler(MessageHandler(filters.Regex("^Дневни операции$"), daily_operations))
    app.add_handler(MessageHandler(filters.Regex("^Операция$"), operation_menu))
    app.add_handler(MessageHandler(filters.Regex("^← Назад$"), back_to_main))
    app.add_handler(MessageHandler(filters.Regex("^Приходи$"), show_prihodi))
    app.add_handler(MessageHandler(filters.Regex("^Разходи$"), show_razhodi))
    app.add_handler(MessageHandler(filters.Regex("^Трансфери$"), show_transfers))

    print("Ботът стартира...")
    app.run_polling()


if __name__ == "__main__":
    main()
