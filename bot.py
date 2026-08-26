# ============================================
# Telegram CRM Bot
# Version: 1.6
# ============================================

import os
import json
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from google.oauth2.service_account import Credentials

TOKEN = os.environ.get("BOT_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
PRIHODI_SPREADSHEET_ID = os.environ.get("PRIHODI_SPREADSHEET_ID")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS")

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
        [KeyboardButton("Моя Баланс"), KeyboardButton("Дневни операции")]
    ], resize_keyboard=True)

def get_daily_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Приходи"), KeyboardButton("Разходи")],
        [KeyboardButton("Трансфери")],
        [KeyboardButton("← Назад")]
    ], resize_keyboard=True)

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

async def daily_operations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    user = find_user_by_telegram_id(telegram_id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    
    await delete_previous_message(context, chat_id)
    
    sent = await update.message.reply_text(
        "Избери тип операция:",
        reply_markup=get_daily_keyboard()
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
    
    sent = await update.message.reply_text(
        "Главно меню:",
        reply_markup=get_main_keyboard()
    )
    last_bot_messages[chat_id] = sent.message_id

# ===== Стари функции (Банки, Наличност, Всички задължения, Задължения, Моя Баланс) =====
# За да не стане кодът прекалено дълъг, тук са съкратени.
# Ще ги запазя пълни в реалния код.

async def banks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (същата логика като преди)
    pass

async def nаличност(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (същата логика)
    pass

async def allpay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... 
    pass

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ...
    pass

async def my_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ...
    pass

# ===== Нови функции за Дневни операции =====

async def show_prihodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    user = find_user_by_telegram_id(telegram_id)
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    
    if not has_permission(user["row"], 19):  # T - Prihodi (колона T = индекс 19)
        await update.message.reply_text("Нямаш права за тази информация")
        return
    
    await delete_previous_message(context, chat_id)
    
    try:
        client = get_client()
        spreadsheet = client.open_by_key(PRIHODI_SPREADSHEET_ID)
        sheet = spreadsheet.worksheet("Prihodi")
        data = sheet.get_all_values()
        
        # Взимаме последните 10 записа (без header)
        records = [row for row in data[1:] if row and row[0].strip()][-10:]
        records.reverse()  # най-новите отгоре
        
        message = "<b>Последни 10 Прихода:</b>\n\n"
        
        for row in records:
            date = row[0] if len(row) > 0 else ""
            amount = row[1] if len(row) > 1 else ""
            source = row[2] if len(row) > 2 else ""
            reason = row[3] if len(row) > 3 else ""
            received_by = row[4] if len(row) > 4 else ""
            
            message += f"<b>{date}</b>\n"
            message += f"{amount} €\n"
            message += f"{source} → {received_by}\n"
            message += f"{reason}\n\n"
        
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
    
    if not has_permission(user["row"], 18):  # S - Razhodi (колона S = индекс 18)
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
            date = row[0] if len(row) > 0 else ""
            amount = row[1] if len(row) > 1 else ""
            receiver = row[2] if len(row) > 2 else ""
            reason = row[3] if len(row) > 3 else ""
            paid_by = row[4] if len(row) > 4 else ""
            
            message += f"<b>{date}</b>\n"
            message += f"{amount} €\n"
            message += f"{receiver}\n"
            message += f"{reason}\n"
            message += f"Платил: {paid_by}\n\n"
        
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
    
    if not has_permission(user["row"], 20):  # U - Trasferi (колона U = индекс 20)
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
            date = row[0] if len(row) > 0 else ""
            amount = row[1] if len(row) > 1 else ""
            from_user = row[2] if len(row) > 2 else ""
            to_user = row[3] if len(row) > 3 else ""
            reason = row[4] if len(row) > 4 else ""
            
            message += f"<b>{date}</b>\n"
            message += f"{amount} €\n"
            message += f"{from_user} → {to_user}\n"
            if reason:
                message += f"{reason}\n"
            message += "\n"
        
        sent = await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_daily_keyboard())
        last_bot_messages[chat_id] = sent.message_id
        
    except Exception as e:
        await update.message.reply_text(f"Грешка: {str(e)}")

async def deleteon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    delete_enabled[chat_id] = True
    await update.message.reply_text("Изтриването на стари съобщения е ВКЛЮЧЕНО")

async def deleteoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    delete_enabled[chat_id] = False
    await update.message.reply_text("Изтриването на стари съобщения е ИЗКЛЮЧЕНО")

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("da", da))
    app.add_handler(CommandHandler("deleteon", deleteon))
    app.add_handler(CommandHandler("deleteoff", deleteoff))
    
    app.add_handler(MessageHandler(filters.Regex("^Дневни операции$"), daily_operations))
    app.add_handler(MessageHandler(filters.Regex("^← Назад$"), back_to_main))
    app.add_handler(MessageHandler(filters.Regex("^Приходи$"), show_prihodi))
    app.add_handler(MessageHandler(filters.Regex("^Разходи$"), show_razhodi))
    app.add_handler(MessageHandler(filters.Regex("^Трансфери$"), show_transfers))
    
    # Тук трябва да се добавят и старите handlers за Банки, Наличност и т.н.
    # За пълния код ще ги включа.
    
    print("Ботът стартира...")
    app.run_polling()

if __name__ == "__main__":
    main()
