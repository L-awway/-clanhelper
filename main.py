import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup

# --- НАСТРОЙКИ ---
API_ID = int(os.environ.get("TELEGRAM_API_ID"))
API_HASH = os.environ.get("TELEGRAM_API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")
MANAGER_BOT_TOKEN = os.environ.get("MANAGER_BOT_TOKEN") 

ADMIN_IDS = [5002413408] 
GAME_BOT = "anicardplaybot"

userbot = Client("ani_helper", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)
manager_bot = Client("manager", api_id=API_ID, api_hash=API_HASH, bot_token=MANAGER_BOT_TOKEN, in_memory=True)

async def send_to_admins(text, markup=None, photo=None):
    for admin_id in ADMIN_IDS:
        try:
            if photo:
                await manager_bot.send_photo(chat_id=admin_id, photo=photo, caption=text, reply_markup=markup, parse_mode="html")
            elif text:
                await manager_bot.send_message(chat_id=admin_id, text=text, reply_markup=markup, parse_mode="html")
        except Exception as e:
            print(f"Ошибка отправки: {e}")

# --- 1. ЛОВИМ ВСЁ В ИГРЕ (Текст, Фото, Кнопки) ---
@userbot.on_message(filters.user(GAME_BOT))
@userbot.on_edited_message(filters.user(GAME_BOT))
async def game_bot_handler(client: Client, message: Message):
    text = message.text or message.caption or ""
    
    # Обработка кнопок
    admin_buttons = []
    
    # 1. Если есть Inline-кнопки (карты в бою)
    if message.reply_markup and isinstance(message.reply_markup, InlineKeyboardMarkup):
        for row in message.reply_markup.inline_keyboard:
            admin_row = []
            for btn in row:
                admin_row.append(InlineKeyboardButton(
                    text=btn.text, 
                    callback_data=f"hit|{message.chat.id}|{message.id}|{btn.callback_data}"
                ))
            admin_buttons.append(admin_row)

    # 2. Если есть Reply-кнопки (нижнее меню)
    if message.reply_markup and isinstance(message.reply_markup, ReplyKeyboardMarkup):
        for row in message.reply_markup.keyboard:
            admin_row = []
            for btn in row:
                admin_row.append(InlineKeyboardButton(
                    text=btn.text,
                    callback_data=btn.text 
                ))
            admin_buttons.append(admin_row)

    markup = InlineKeyboardMarkup(admin_buttons) if admin_buttons else None

    if not text and message.photo:
        text = "*(Прислано фото)*"
    elif not text and markup:
        text = "*(Присланы кнопки)*"
    elif not text:
        text = "*(Пустое сообщение)*"

    final_text = f"🎮 **Событие:**\n\n{text}"

    if message.photo:
        await send_to_admins(final_text, markup=markup, photo=message.photo.file_id)
    else:
        await send_to_admins(final_text, markup=markup)

# --- 2. МЕНЮ УПРАВЛЕНИЯ ---
@manager_bot.on_message(filters.command("start") & filters.user(ADMIN_IDS))
async def start_handler(client: Client, message: Message):
    await message.reply("👋 **Привет!** Используй `/menu` для управления.")

@manager_bot.on_message(filters.command("menu") & filters.user(ADMIN_IDS))
async def menu_handler(client: Client, message: Message):
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏟 Арена", callback_data="🏟 Арена"), InlineKeyboardButton("🛡 Кланы", callback_data="🛡 Кланы")],
        [InlineKeyboardButton("📜 Меню", callback_data="📜 Меню")]
    ])
    await message.reply("Выбери, куда отправить Твинка:", reply_markup=markup)

# --- 3. ОБРАБОТКА НАЖАТИЙ ---
@manager_bot.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    if callback_query.from_user.id not in ADMIN_IDS:
        return await callback_query.answer("Нет доступа")

    data = callback_query.data

    if data.startswith("hit|"):
        parts = data.split("|")
        chat_id = int(parts[1])
        msg_id = int(parts[2])
        real_cb_data = parts[3].encode()
        try:
            await userbot.request_callback_answer(chat_id=chat_id, message_id=msg_id, callback_data=real_cb_data)
            await callback_query.answer("✅ Ход сделан!")
        except Exception as e:
            await callback_query.answer(f"Ошибка: {e}", show_alert=True)
        return

    try:
        await userbot.send_message(GAME_BOT, data)
        await callback_query.answer(f"✅ Отправлено: {data}")
    except Exception as e:
        await callback_query.answer(f"Ошибка: {e}", show_alert=True)

# --- 4. ОБЫЧНЫЙ ТЕКСТ ---
@manager_bot.on_message(filters.user(ADMIN_IDS) & filters.text & ~filters.command(["start", "menu"]))
async def text_command_handler(client: Client, message: Message):
    game_text = message.text
    try:
        await userbot.send_message(GAME_BOT, game_text)
        await message.reply(f"✅ Отправлено в игру: {game_text}")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

# --- ЗАПУСК ---
async def main():
    print("Запускаем...")
    await userbot.start()
    await manager_bot.start()
    print("Бот работает.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
