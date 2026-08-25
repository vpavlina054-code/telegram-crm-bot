import os
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import gspread
from google.oauth2.service_account import Credentials

TOKEN = os.environ.get("BOT_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS")

# Тук пазим ID на последното съобщение на бота за всеки потребител
last_bot_messages = {}

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

async def delete_previous_message(context, chat_id):
    """Изтрива предишното съобщение на бота, ако има такова"""
    if chat_id in last_bot_messages:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_bot_messages[chat_id])
        except:
            pass  # Ако вече е изтрито или е твърде старо – просто продължаваме

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    user = find_user_by_telegram_id(telegram_id)
    
    if user is None:
        await update.message.reply_text("Този бот не работи")
        return
    
    # Изтриваме старото съобщение на бота
    await delete_previous_message(context, chat_id)
    
    # Изпращаме новото
    sent = await update.message.reply_text(f"Здравей, {user['user']}! Имаш достъп.")
    
    # Запазваме ID-то на новото съобщение
    last_bot_messages[chat_id] = sent.message_id

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("Ботът стартира...")
    app.run_polling()

if __name__ == "__main__":
    main()
