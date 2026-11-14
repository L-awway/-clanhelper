import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# --- НАСТРОЙКИ (БЕРУТСЯ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ БОТХОСТА) ---
API_ID = int(os.environ.get("TELEGRAM_API_ID"))
API_HASH = os.environ.get("TELEGRAM_API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

# ТОКЕН ТВОЕГО БОТА ОТ BOTFATHER
MANAGER_BOT_TOKEN = os.environ.get("MANAGER_BOT_TOKEN") 

# СЮДА ВПИШИ СВОЙ ID (узнать у @userinfobot)
# Можно добавить несколько через запятую: [123456, 789012]
ADMIN_IDS = [5002413408] 

GAME_BOT = "anicardplaybot"

# 1. ЮЗЕРБОТ (работает от лица Твинка, играет)
userbot = Client(
    name="ani_helper",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)

# 2. БОТ-МЕНЕДЖЕР (с ним ты общаешься)
manager_bot = Client(
    name="manager",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=MANAGER_BOT_TOKEN,
    in_memory=True
)

# --- ЛОВИМ ИГРУ В ЮЗЕРБОТЕ (Твинке) ---
@userbot.on_message(filters.user(GAME_BOT))
async def game_bot_handler(client: Client, message: Message):
    # Формируем текст, который придет тебе
    text = f"🎮 **Событие в игре (Твинк):**\n\n{message.text}"
    
    # Если есть кнопки — переносим их
    if message.reply_markup:
        admin_buttons = []
        for row in message.reply_markup.inline_keyboard:
            admin_row = []
            for btn in row:
                admin_row.append(InlineKeyboardButton(
                    text=btn.text, 
                    # В данных кнопки прячем ID сообщения в игре и данные самой кнопки
                    callback_data=f"hit|{message.chat.id}|{message.id}|{btn.callback_data}"
                ))
            admin_buttons.append(admin_row)
        markup = InlineKeyboardMarkup(admin_buttons)
    else:
        markup = None

    # Отправляем инфу всем админам
    for admin_id in ADMIN_IDS:
        try:
            await manager_bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=markup
            )
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")

# --- ОБЩЕНИЕ С ТОБОЙ (Бот-Менеджер) ---
@manager_bot.on_message(filters.command("start") & filters.user(ADMIN_IDS))
async def start_handler(client: Client, message: Message):
    await message.reply(
        "👋 **Привет, Админ!**\n\n"
        "Я подключен к аккаунту Твинка (Юзербот).\n"
        "Сейчас я буду пересылать сюда всё, что происходит в AniCard.\n"
        "Когда начнется бой, жми кнопки прямо здесь — Твинк сделает ход."
    )

# --- ЛОВИМ ТВОИ НАЖАТИЯ НА КНОПКИ ---
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
            # Юзербот (Твинк) нажимает кнопку в игре
            await userbot.request_callback_answer(
                chat_id=chat_id,
                message_id=msg_id,
                callback_data=real_cb_data
            )
            await callback_query.answer("✅ Ход сделан от лица Твинка!")
            # Удаляем сообщение у тебя, чтобы не засорять чат (по желанию)
            await callback_query.message.delete() 
        except Exception as e:
            await callback_query.answer(f"Ошибка: {e}", show_alert=True)

# --- ЗАПУСК ---
async def main():
    print("Запускаем систему...")
    await userbot.start()
    await manager_bot.start()
    print("Всё работает! Ждем боя.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
