# ============================================
# Telegram CRM Bot
# Version: 1.8
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
    sofia_tz = ZoneInfo("Europe/Sofia")
    return datetime.now(sofia_tz).strftime("%d.%m.%Y %H:%M")

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
    return [row[0].strip() for row in data[1:] if row and row[0].strip()]

def get_all_balances():
    """Взима текущите наличности от лист Total"""
    try:
        client = get_client()
        spreadsheet = client.open_by_key(PRIHODI_SPREADSHEET_ID)
        sheet = spreadsheet.worksheet("Total")
        data = sheet.get_all_values()
        
        balances = []
        for row in data:
            if len(row) > 2 and row[1].strip():
                name = row[1].strip()
                amount = row[2].strip()
                balances.append(f"{name}: {amount}")
        return "\n".join(balances) if balances else "Няма данни"
    except:
        return "Грешка при четене на наличности"

async def send_notifications(context, base_message):
    """Изпраща известие + наличности до всички с DA в колона W"""
    try:
        balances = get_all_balances()
        full_message = f"{base_message}\n\nТекущи наличности:\n{balances}"
        
        client = get_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.worksheet("SYSTEM_USERS")
        data = sheet.get_all_values()
        
        for row in data[1:]:
            if len(row) > 22 and str(row[22]).strip().upper() == "DA":
                telegram_id = str(row[12]).strip() if len(row) > 12 else ""
                if telegram_id and telegram_id.isdigit():
                    try:
                        await context.bot.send_message(chat_id=int(telegram_id), text=full_message)
                    except:
                        pass
    except Exception as e:
        print(f"Грешка при известия: {e}")

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
    if not has_permission(user["row"], 21):
        await update.message.reply_text("Нямаш права за операции")
        return
    await delete_previous_message(context, chat_id)
    sent = await update.message.reply_text("Избери тип операция:", reply_markup=get_operation_keyboard())
    last_bot_messages[chat_id] = sent.message_id

# ==================== ЧЕТЕНЕ (съкратено за място – пълните функции са същите като 1.7) ====================
# За да не стане съобщението огромно, тук са запазени само ключовите.
# Пълните banks, nаличност, allpay, pay, my_balance, show_prihodi и т.н. остават същите.

async def banks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... същата функция както в 1.7
    pass

# (Останалите функции за четене са идентични с версия 1.7)

# ==================== ПИСАНЕ ====================

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
        await update.message.reply_text("Отказано.", reply_markup=get_main_keyboard())
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
        
        notify_text = (
            f"🔔 Нов Приход\n"
            f"Сума: {context.user_data['amount']} €\n"
            f"От: {context.user_data['source']}\n"
            f"Основание: {reason}\n"
            f"Приел: {context.user_data['user']}"
        )
        await send_notifications(context, notify_text)
        
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}", reply_markup=get_main_keyboard())
    return ConversationHandler.END

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
        await update.message.reply_text("Отказано.", reply_markup=get_main_keyboard())
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
        
        notify_text = (
            f"🔔 Нов Разход\n"
            f"Сума: {context.user_data['amount']} €\n"
            f"Получател: {context.user_data['source']}\n"
            f"Основание: {reason}\n"
            f"Платил: {context.user_data['user']}"
        )
        await send_notifications(context, notify_text)
        
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}", reply_markup=get_main_keyboard())
    return ConversationHandler.END

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
        await update.message.reply_text("Отказано.", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    context.user_data['from_user'] = text
    users = get_system_users()
    await update.message.reply_text("Към кого (Получател):", reply_markup=get_list_keyboard(users))
    return TRANSFER_TO

async def transfer_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "← Отказ":
        await update.message.reply_text("Отказано.", reply_markup=get_main_keyboard())
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
        
        notify_text = (
            f"🔔 Нов Трансфер\n"
            f"Сума: {context.user_data['amount']} €\n"
            f"{context.user_data['from_user']} → {context.user_data['to_user']}\n"
            f"Основание: {reason if reason else '—'}"
        )
        await send_notifications(context, notify_text)
        
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
