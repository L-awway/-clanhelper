import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# --- НАСТРОЙКИ ---
API_ID = int(os.environ.get("TELEGRAM_API_ID"))
API_HASH = os.environ.get("TELEGRAM_API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")
MANAGER_BOT_TOKEN = os.environ.get("MANAGER_BOT_TOKEN") 

ADMIN_IDS = [5002413408] 
GAME_BOT = "anicardplaybot"

print("1. Переменные загружены. Инициализация клиентов...")

# 1. ЮЗЕРБОТ
userbot = Client(
    name="ani_helper",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)

# 2. БОТ-МЕНЕДЖЕР
# Указываем api_id и api_hash, чтобы Pyrogram не ругался
manager_bot = Client(
    name="manager",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=MANAGER_BOT_TOKEN,
    in_memory=True
)

# --- ХЕНДЛЕРЫ ---
@userbot.on_message(filters.user(GAME_BOT))
async def game_bot_handler(client: Client, message: Message):
    print(f"Поймано сообщение от AniCard: {message.id}")
    text = f"🎮 **Событие в игре (Твинк):**\n\n{message.text}"
    
    if message.reply_markup:
        admin_buttons = []
        for row in message.reply_markup.inline_keyboard:
            admin_row = []
            for btn in row:
                admin_row.append(InlineKeyboardButton(
                    text=btn.text, 
                    callback_data=f"hit|{message.chat.id}|{message.id}|{btn.callback_data}"
                ))
            admin_buttons.append(admin_row)
        markup = InlineKeyboardMarkup(admin_buttons)
    else:
        markup = None

    for admin_id in ADMIN_IDS:
        try:
            await manager_bot.send_message(chat_id=admin_id, text=text, reply_markup=markup)
            print(f"Отправлено админу {admin_id}")
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")

@manager_bot.on_message(filters.command("start") & filters.user(ADMIN_IDS))
async def start_handler(client: Client, message: Message):
    print(f"Получена команда /start от {message.from_user.id}")
    await message.reply("👋 **Привет, Админ!** Я готов к работе.")

@manager_bot.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    if callback_query.from_user.id not in ADMIN_IDS:
        return await callback_query.answer("Нет доступа")

    data = callback_query.data.split("|")
    if data[0] == "hit":
        chat_id = int(data[1])
        msg_id = int(data[2])
        real_cb_data = data[3].encode()

        try:
            await userbot.request_callback_answer(chat_id=chat_id, message_id=msg_id, callback_data=real_cb_data)
            await callback_query.answer("✅ Ход сделан!")
            await callback_query.message.delete() 
        except Exception as e:
            await callback_query.answer(f"Ошибка: {e}", show_alert=True)

# --- ЗАПУСК (С ЛОГАМИ) ---
async def main():
    print("Запускаем Юзербота...")
    await userbot.start()
    print("Юзербот успешно запущен!")
    
    print("Запускаем Бота-менеджера...")
    await manager_bot.start()
    print("Бот-менеджер успешно запущен! Ждем сообщений.")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    print("=== СТАРТ БОТА ===")
    asyncio.run(main())
