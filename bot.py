# ============================================
# Telegram CRM Bot
# Version: 1.7
# ============================================

import os
import json
from datetime import datetime
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

# Състояния
AMOUNT, SOURCE, REASON, TRANSFER_FROM, TRANSFER_TO = range(5)

last_bot_messages = {}
delete_enabled = {}

def get_client():
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def find_user_by_telegram_id(telegram_id):
    client = get_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    sheet = spreadsheet.worksheet("SYSTEM_USERS")
    data = sheet.get_all_values()
    for row in data[1:]:
        if len(row) > 12 and str(row[12]).strip() == str(telegram_id):
            return {"user": row[0], "row": row}
    return None

def has_permission(user_row, column_index):
    if len(user_row) > column_index:
        return str(user_row[column_index]).strip().upper() == "DA"
    return False

def get_current_datetime():
    return datetime.now().strftime("%d.%m.%Y %H:%M")

def get_unique_list_from_column(sheet_name, column_index):
    client = get_client()
    spreadsheet = client.open_by_key(PRIHODI_SPREADSHEET_ID)
    sheet = spreadsheet.worksheet(sheet_name)
    data = sheet.get_all_values()
    values = set()
    for row in data[1:]:
        if len(row) > column_index and row[column_index].strip():
            values.add(row[column_index].strip())
    return sorted(list(values))

def get_system_users():
    client = get_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    sheet = spreadsheet.worksheet("SYSTEM_USERS")
    data = sheet.get_all_values()
    users = []
    for row in data[1:]:
        if row and row[0].strip():
            users.append(row[0].strip())
    return users

async def delete_previous_message(context, chat_id):
    if delete_enabled.get(chat_id, True) and chat_id in last_bot_messages:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_bot_messages[chat_id])
        except:
            pass

def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Банки"), KeyboardButton("Наличност")],
        [KeyboardButton("Всички задължения"), KeyboardButton("Задължения")],
        [KeyboardButton("Моя Баланс"), KeyboardButton("Дневни операции")],
        [KeyboardButton("Операция")]
    ], resize_keyboard=True)

def get_daily_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Приходи"), KeyboardButton("Разходи")],
        [KeyboardButton("Трансфери")],
        [KeyboardButton("← Назад")]
    ], resize_keyboard=True)

def get_operation_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Приход"), KeyboardButton("Разход")],
        [KeyboardButton("Трансфер")],
        [KeyboardButton("← Назад")]
    ], resize_keyboard=True)

def get_list_keyboard(items):
    keyboard = []
    row = []
    for item in items:
        row.append(KeyboardButton(item))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([KeyboardButton("← Отказ")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==================== ОСНОВНИ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Този бот не работи")

async def da(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    await delete_previous_message(context, chat_id)
    sent = await update.message.reply_text(
        f"Здравей, {user['user']}!\nИзбери опция:",
        reply_markup=get_main_keyboard()
    )
    last_bot_messages[chat_id] = sent.message_id

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    await delete_previous_message(context, chat_id)
    sent = await update.message.reply_text("Главно меню:", reply_markup=get_main_keyboard())
    last_bot_messages[chat_id] = sent.message_id

async def daily_operations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    await delete_previous_message(context, chat_id)
    sent = await update.message.reply_text("Избери тип операция:", reply_markup=get_daily_keyboard())
    last_bot_messages[chat_id] = sent.message_id

async def operation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    if not has_permission(user["row"], 21):  # V - Paynow
        await update.message.reply_text("Нямаш права за операции")
        return
    await delete_previous_message(context, chat_id)
    sent = await update.message.reply_text("Избери тип операция:", reply_markup=get_operation_keyboard())
    last_bot_messages[chat_id] = sent.message_id

# ==================== ЧЕТЕНЕ ====================

async def banks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    if not has_permission(user["row"], 13):
        await update.message.reply_text("Нямаш права за тази информация")
        return
    await delete_previous_message(context, chat_id)
    try:
        client = get_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.worksheet("LiveStatus")
        data = sheet.get_all_values()
        update_info = data[1][0] if len(data) > 1 else "Няма данни"
        start_idx = total_idx = None
        for i, row in enumerate(data):
            if len(row) > 0 and "БАНКОВИ НАЛИЧНОСТИ" in str(row[0]).upper():
                start_idx = i
            if len(row) > 0 and "ОБЩО БАНКИ" in str(row[0]).upper():
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
        sent = await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_main_keyboard())
        last_bot_messages[chat_id] = sent.message_id
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")

async def nаличност(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    if not has_permission(user["row"], 14):
        await update.message.reply_text("Нямаш права за тази информация")
        return
    await delete_previous_message(context, chat_id)
    try:
        client = get_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.worksheet("LiveStatus")
        data = sheet.get_all_values()
        update_info = data[1][0] if len(data) > 1 else "Няма данни"
        start_idx = end_idx = None
        for i, row in enumerate(data):
            if len(row) > 0 and "КАСА И НЕРАЗПРЕДЕЛЕНИ" in str(row[0]).upper():
                start_idx = i
            if len(row) > 0 and "ЗАДЪЛЖЕНИЯ КЪМ ОБЕКТИ" in str(row[0]).upper():
                end_idx = i
                break
        if start_idx is None or end_idx is None:
            await update.message.reply_text("Не мога да намеря секцията")
            return
        items = []
        for i in range(start_idx + 1, end_idx):
            row = data[i]
            if len(row) > 0 and row[0].strip():
                value = row[2].strip() if len(row) > 2 else ""
                if value:
                    items.append((row[0].strip(), value))
        message = f"<b>{update_info}</b>\n\n<b>КАСА И НЕРАЗПРЕДЕЛЕНИ</b>\n\n"
        for label, value in items:
            message += f"{label}\n<b>{value}</b>\n\n"
        sent = await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_main_keyboard())
        last_bot_messages[chat_id] = sent.message_id
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")

async def allpay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    if not has_permission(user["row"], 15):
        await update.message.reply_text("Нямаш права за тази информация")
        return
    await delete_previous_message(context, chat_id)
    try:
        client = get_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.worksheet("LiveStatus")
        data = sheet.get_all_values()
        update_info = data[1][0] if len(data) > 1 else "Няма данни"
        start_idx = total_idx = None
        for i, row in enumerate(data):
            if len(row) > 0 and "ЗАДЪЛЖЕНИЯ КЪМ ОБЕКТИ" in str(row[0]).upper():
                start_idx = i
            if len(row) > 0 and "ОБЩО ЗАДЪЛЖЕНИЯ" in str(row[0]).upper():
                total_idx = i
                break
        if start_idx is None or total_idx is None:
            await update.message.reply_text("Не мога да намеря секцията")
            return
        items = []
        for i in range(start_idx + 2, total_idx):
            row = data[i]
            if len(row) > 0 and row[0].strip():
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
        sent = await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_main_keyboard())
        last_bot_messages[chat_id] = sent.message_id
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    if not has_permission(user["row"], 16):
        await update.message.reply_text("Нямаш права за тази информация")
        return
    await delete_previous_message(context, chat_id)
    try:
        client = get_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.worksheet("LiveStatus")
        data = sheet.get_all_values()
        update_info = data[1][0] if len(data) > 1 else "Няма данни"
        start_idx = total_idx = None
        for i, row in enumerate(data):
            if len(row) > 0 and "ЗАДЪЛЖЕНИЯ КЪМ ОБЕКТИ" in str(row[0]).upper():
                start_idx = i
            if len(row) > 0 and "ОБЩО ЗАДЪЛЖЕНИЯ" in str(row[0]).upper():
                total_idx = i
                break
        if start_idx is None or total_idx is None:
            await update.message.reply_text("Не мога да намеря секцията")
            return
        items = []
        for i in range(start_idx + 2, total_idx):
            row = data[i]
            if len(row) > 0 and row[0].strip():
                items.append((row[0].strip(), row[4].strip() if len(row) > 4 else ""))
        message = f"<b>{update_info}</b>\n\n<b>ИЗИСКУЕМИ СУМИ</b>\n\n"
        for name, required in items:
            message += f"<b>{name}</b>\n{required}\n\n"
        sent = await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_main_keyboard())
        last_bot_messages[chat_id] = sent.message_id
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")

async def my_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    if not has_permission(user["row"], 17):
        await update.message.reply_text("Нямаш права за тази информация")
        return
    await delete_previous_message(context, chat_id)
    try:
        client = get_client()
        spreadsheet = client.open_by_key(PRIHODI_SPREADSHEET_ID)
        sheet = spreadsheet.worksheet("Total")
        data = sheet.get_all_values()
        username = user["user"]
        balance = None
        for row in data:
            if len(row) > 1 and row[1].strip() == username:
                balance = row[2].strip() if len(row) > 2 else "—"
                break
        if balance is None:
            await update.message.reply_text(f"Не намерих наличност за {username}")
            return
        message = f"Твоята текуща наличност:\n\n<b>{username}</b>\n<b>{balance}</b>"
        sent = await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_main_keyboard())
        last_bot_messages[chat_id] = sent.message_id
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")

async def show_prihodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    if not has_permission(user["row"], 19):
        await update.message.reply_text("Нямаш права за тази информация")
        return
    await delete_previous_message(context, chat_id)
    try:
        client = get_client()
        spreadsheet = client.open_by_key(PRIHODI_SPREADSHEET_ID)
        sheet = spreadsheet.worksheet("Prihodi")
        data = sheet.get_all_values()
        records = [row for row in data[1:] if row and row[0].strip()][-10:]
        records.reverse()
        message = "<b>Последни 10 Прихода:</b>\n\n"
        for row in records:
            message += f"<b>{row[0]}</b>\n{row[1] if len(row)>1 else ''} €\n{row[2] if len(row)>2 else ''} → {row[4] if len(row)>4 else ''}\n{row[3] if len(row)>3 else ''}\n\n"
        sent = await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_daily_keyboard())
        last_bot_messages[chat_id] = sent.message_id
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")

async def show_razhodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    if not has_permission(user["row"], 18):
        await update.message.reply_text("Нямаш права за тази информация")
        return
    await delete_previous_message(context, chat_id)
    try:
        client = get_client()
        spreadsheet = client.open_by_key(PRIHODI_SPREADSHEET_ID)
        sheet = spreadsheet.worksheet("Razhodi")
        data = sheet.get_all_values()
        records = [row for row in data[1:] if row and row[0].strip()][-10:]
        records.reverse()
        message = "<b>Последни 10 Разхода:</b>\n\n"
        for row in records:
            message += f"<b>{row[0]}</b>\n{row[1] if len(row)>1 else ''} €\n{row[2] if len(row)>2 else ''}\n{row[3] if len(row)>3 else ''}\nПлатил: {row[4] if len(row)>4 else ''}\n\n"
        sent = await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_daily_keyboard())
        last_bot_messages[chat_id] = sent.message_id
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")

async def show_transfers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    if not has_permission(user["row"], 20):
        await update.message.reply_text("Нямаш права за тази информация")
        return
    await delete_previous_message(context, chat_id)
    try:
        client = get_client()
        spreadsheet = client.open_by_key(PRIHODI_SPREADSHEET_ID)
        sheet = spreadsheet.worksheet("Transfers")
        data = sheet.get_all_values()
        records = [row for row in data[1:] if row and row[0].strip()][-10:]
        records.reverse()
        message = "<b>Последни 10 Трансфера:</b>\n\n"
        for row in records:
            message += f"<b>{row[0]}</b>\n{row[1] if len(row)>1 else ''} €\n{row[2] if len(row)>2 else ''} → {row[3] if len(row)>3 else ''}\n"
            if len(row) > 4 and row[4]:
                message += f"{row[4]}\n"
            message += "\n"
        sent = await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_daily_keyboard())
        last_bot_messages[chat_id] = sent.message_id
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")

# ==================== ПИСАНЕ - ПРИХОД ====================

async def prihod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None or not has_permission(user["row"], 21):
        await update.message.reply_text("Нямаш права")
        return ConversationHandler.END
    context.user_data.clear()
    context.user_data['user'] = user['user']
    await update.message.reply_text("Въведи сума за Приход:", reply_markup=ReplyKeyboardRemove())
    return AMOUNT

async def prihod_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", ".")
    try:
        context.user_data['amount'] = float(text)
    except:
        await update.message.reply_text("Моля, въведи валидно число:")
        return AMOUNT
    sources = get_unique_list_from_column("Prihodi", 2) or ["KASA", "Друг"]
    await update.message.reply_text("Избери от кого е приходът:", reply_markup=get_list_keyboard(sources))
    return SOURCE

async def prihod_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "← Отказ":
        await update.message.reply_text("Отказano.", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    context.user_data['source'] = text
    await update.message.reply_text("Напиши основание:", reply_markup=ReplyKeyboardRemove())
    return REASON

async def prihod_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    try:
        client = get_client()
        sheet = client.open_by_key(PRIHODI_SPREADSHEET_ID).worksheet("Prihodi")
        sheet.append_row([
            get_current_datetime(),
            context.user_data['amount'],
            context.user_data['source'],
            reason,
            context.user_data['user']
        ])
        await update.message.reply_text(
            f"✅ Успешен Приход!\nСума: {context.user_data['amount']} €\nОт: {context.user_data['source']}\nОснование: {reason}",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}", reply_markup=get_main_keyboard())
    return ConversationHandler.END

# ==================== ПИСАНЕ - РАЗХОД ====================

async def razhod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None or not has_permission(user["row"], 21):
        await update.message.reply_text("Нямаш права")
        return ConversationHandler.END
    context.user_data.clear()
    context.user_data['user'] = user['user']
    await update.message.reply_text("Въведи сума за Разход:", reply_markup=ReplyKeyboardRemove())
    return AMOUNT

async def razhod_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", ".")
    try:
        context.user_data['amount'] = float(text)
    except:
        await update.message.reply_text("Моля, въведи валидно число:")
        return AMOUNT
    receivers = get_unique_list_from_column("Razhodi", 2) or ["Друг"]
    await update.message.reply_text("Избери получател:", reply_markup=get_list_keyboard(receivers))
    return SOURCE

async def razhod_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "← Отказ":
        await update.message.reply_text("Отказano.", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    context.user_data['source'] = text
    await update.message.reply_text("Напиши основание:", reply_markup=ReplyKeyboardRemove())
    return REASON

async def razhod_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    try:
        client = get_client()
        sheet = client.open_by_key(PRIHODI_SPREADSHEET_ID).worksheet("Razhodi")
        sheet.append_row([
            get_current_datetime(),
            context.user_data['amount'],
            context.user_data['source'],
            reason,
            context.user_data['user']
        ])
        await update.message.reply_text(
            f"✅ Успешен Разход!\nСума: {context.user_data['amount']} €\nПолучател: {context.user_data['source']}\nОснование: {reason}",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}", reply_markup=get_main_keyboard())
    return ConversationHandler.END

# ==================== ПИСАНЕ - ТРАНСФЕР ====================

async def transfer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = find_user_by_telegram_id(telegram_id)
    if user is None or not has_permission(user["row"], 21):
        await update.message.reply_text("Нямаш права")
        return ConversationHandler.END
    context.user_data.clear()
    context.user_data['user'] = user['user']
    await update.message.reply_text("Въведи сума за Трансфер:", reply_markup=ReplyKeyboardRemove())
    return AMOUNT

async def transfer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", ".")
    try:
        context.user_data['amount'] = float(text)
    except:
        await update.message.reply_text("Моля, въведи валидно число:")
        return AMOUNT
    users = get_system_users()
    await update.message.reply_text("От кого (Изпращач):", reply_markup=get_list_keyboard(users))
    return TRANSFER_FROM

async def transfer_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "← Отказ":
        await update.message.reply_text("Отказano.", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    context.user_data['from_user'] = text
    users = get_system_users()
    await update.message.reply_text("Към кого (Получател):", reply_markup=get_list_keyboard(users))
    return TRANSFER_TO

async def transfer_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "← Отказ":
        await update.message.reply_text("Отказano.", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    context.user_data['to_user'] = text
    await update.message.reply_text("Основание (или - ако няма):", reply_markup=ReplyKeyboardRemove())
    return REASON

async def transfer_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    if reason == "-":
        reason = ""
    try:
        client = get_client()
        sheet = client.open_by_key(PRIHODI_SPREADSHEET_ID).worksheet("Transfers")
        sheet.append_row([
            get_current_datetime(),
            context.user_data['amount'],
            context.user_data['from_user'],
            context.user_data['to_user'],
            reason
        ])
        await update.message.reply_text(
            f"✅ Успешен Трансфер!\n{context.user_data['from_user']} → {context.user_data['to_user']}\nСума: {context.user_data['amount']} €",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}", reply_markup=get_main_keyboard())
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операцията е отменена.", reply_markup=get_main_keyboard())
    return ConversationHandler.END

async def deleteon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    delete_enabled[chat_id] = True
    await update.message.reply_text("Изтриването е ВКЛЮЧЕНО")

async def deleteoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    delete_enabled[chat_id] = False
    await update.message.reply_text("Изтриването е ИЗКЛЮЧЕНО")

# ==================== MAIN ====================

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
    app.add_handler(CommandHandler("deleteon", deleteon))
    app.add_handler(CommandHandler("deleteoff", deleteoff))

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
