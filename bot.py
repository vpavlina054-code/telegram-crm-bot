# ============================================
# Telegram CRM Bot
# Version: 1.3
# ============================================

import os
import json
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from google.oauth2.service_account import Credentials

TOKEN = os.environ.get("BOT_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
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
            return {
                "user": row[0],
                "row": row
            }
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
    
    keyboard = [
        [KeyboardButton("Банки")],
        [KeyboardButton("Наличност")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    sent = await update.message.reply_text(
        f"Здравей, {user['user']}!\nИзбери опция:",
        reply_markup=reply_markup
    )
    last_bot_messages[chat_id] = sent.message_id

async def banks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    user = find_user_by_telegram_id(telegram_id)
    
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    
    # Колона N = индекс 13 (BankiStatus)
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
        
        start_idx = None
        total_idx = None
        
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
                firm = row[0].strip()
                date = row[1].strip() if len(row) > 1 else ""
                balance = row[2].strip() if len(row) > 2 else ""
                firms.append((firm, date, balance))
        
        total_row = data[total_idx]
        total_sum = total_row[2].strip() if len(total_row) > 2 else "—"
        
        message = f"<b>{update_info}</b>\n\n"
        message += "<b>БАНКОВИ НАЛИЧНОСТИ</b>\n\n"
        
        for firm, date, balance in firms:
            message += f"<b>{firm}</b>\n"
            message += f"{date}  |  {balance}\n\n"
        
        message += "────────────────\n"
        message += f"<b>ОБЩО БАНКИ:</b> {total_sum}"
        
        sent = await update.message.reply_text(message, parse_mode="HTML")
        last_bot_messages[chat_id] = sent.message_id
        
    except Exception as e:
        await update.message.reply_text(f"Грешка при четене: {str(e)}")

async def nаличност(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    user = find_user_by_telegram_id(telegram_id)
    
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    
    # Колона O = индекс 14 (KasaFinal)
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
        
        start_idx = None
        end_idx = None
        
        for i, row in enumerate(data):
            if len(row) > 0 and "КАСА И НЕРАЗПРЕДЕЛЕНИ" in str(row[0]).upper():
                start_idx = i
            if len(row) > 0 and "ЗАДЪЛЖЕНИЯ КЪМ ОБЕКТИ" in str(row[0]).upper():
                end_idx = i
                break
        
        if start_idx is None or end_idx is None:
            await update.message.reply_text("Не мога да намеря секцията с наличностите")
            return
        
        items = []
        for i in range(start_idx + 1, end_idx):
            row = data[i]
            if len(row) > 0 and row[0].strip():
                label = row[0].strip()
                value = row[2].strip() if len(row) > 2 else ""
                if value:  # само ако има сума
                    items.append((label, value))
        
        message = f"<b>{update_info}</b>\n\n"
        message += "<b>КАСА И НЕРАЗПРЕДЕЛЕНИ</b>\n\n"
        
        for label, value in items:
            message += f"{label}\n"
            message += f"<b>{value}</b>\n\n"
        
        sent = await update.message.reply_text(message, parse_mode="HTML")
        last_bot_messages[chat_id] = sent.message_id
        
    except Exception as e:
        await update.message.reply_text(f"Грешка при четене: {str(e)}")

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
    app.add_handler(MessageHandler(filters.Regex("^Банки$"), banks))
    app.add_handler(MessageHandler(filters.Regex("^Наличност$"), nаличност))
    print("Ботът стартира...")
    app.run_polling()

if __name__ == "__main__":
    main()


# ============================================
# ОПИСАНИЕ НА БУТОНИТЕ
# ============================================
# Банки      → Показва моментното състояние на всички банкови сметки + обща сума
# Наличност  → Показва касата, неразпределените суми и салдата по касиери
# ============================================
