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

# 1. ЮЗЕРБОТ (Твинк)
userbot = Client(
    name="ani_helper",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)

# 2. БОТ-МЕНЕДЖЕР (с ним общаешься ты)
manager_bot = Client(
    name="manager",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=MANAGER_BOT_TOKEN,
    in_memory=True
)

# Функция для отправки сообщений тебе
async def send_to_admins(text, markup=None, photo=None):
    for admin_id in ADMIN_IDS:
        try:
            if photo:
                await manager_bot.send_photo(chat_id=admin_id, photo=photo, caption=text, reply_markup=markup)
            elif text:
                await manager_bot.send_message(chat_id=admin_id, text=text, reply_markup=markup)
        except Exception as e:
            print(f"Ошибка отправки: {e}")

# --- 1. ЛОВИМ ВСЁ, ЧТО ПРОИСХОДИТ В ИГРЕ ---
@userbot.on_message(filters.user(GAME_BOT))
@userbot.on_edited_message(filters.user(GAME_BOT))
async def game_bot_handler(client: Client, message: Message):
    if not message.text and not message.caption and not message.photo:
        return

    text = message.text or message.caption or "*(Медиа-файл без текста)*"
    
    # Обработка Inline-кнопок (выбор карт в бою)
    markup = None
    if message.reply_markup and isinstance(message.reply_markup, InlineKeyboardMarkup):
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

    # Отправляем фото или текст
    if message.photo:
        await send_to_admins(f"🎮 **Событие (Фото):**\n\n{text}", markup=markup, photo=message.photo.file_id)
    elif text != "None":
        await send_to_admins(f"🎮 **Событие:**\n\n{text}", markup=markup)


# --- 2. ГЛАВНОЕ МЕНЮ С ТОЧНЫМИ ЭМОДЗИ ---
@manager_bot.on_message(filters.command("start") & filters.user(ADMIN_IDS))
async def start_handler(client: Client, message: Message):
    await message.reply("👋 **Привет, Админ!** Напиши /menu, чтобы управлять Твинком.")

@manager_bot.on_message(filters.command("menu") & filters.user(ADMIN_IDS))
async def menu_handler(client: Client, message: Message):
    # В callback_data передаем ТОЧНЫЙ текст с эмодзи
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏟 Арена", callback_data="🏟 Арена"), InlineKeyboardButton("🎒 Профиль", callback_data="🎒 Профиль")],
        [InlineKeyboardButton("🛡 Кланы", callback_data="clan_menu"), InlineKeyboardButton("🛍 Магазин", callback_data="🛍 Магазин")],
        [InlineKeyboardButton("🃏 Мои карты", callback_data="🃏 Мои карты"), InlineKeyboardButton("🔍 Лиговый бой", callback_data="🔍 Лиговый бой")],
        [InlineKeyboardButton("⚖️ Обмен карт", callback_data="⚖️ Обмен карт"), InlineKeyboardButton("🪙 Омут душ", callback_data="🪙 Омут душ")],
        [InlineKeyboardButton("📜 Меню", callback_data="📜 Меню")]
    ])
    await message.reply("Выбери, куда отправить Твинка:", reply_markup=markup)


# --- 3. ПОДМЕНЮ КЛАНОВ (С ТОЧНЫМИ ЭМОДЗИ) ---
@manager_bot.on_callback_query(filters.regex(r"^clan_menu$") & filters.user(ADMIN_IDS))
async def clan_menu_handler(client: Client, callback_query: CallbackQuery):
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡 Мой клан", callback_data="🛡 Мой клан")],
        [InlineKeyboardButton("🔙 В главное меню", callback_data="🔙 В главное меню")]
    ])
    await callback_query.message.edit_text("🛡 **Меню Кланов:**", reply_markup=markup)


# --- 4. ОБРАБОТКА НАЖАТИЙ ---
@manager_bot.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    if callback_query.from_user.id not in ADMIN_IDS:
        return await callback_query.answer("Нет доступа")

    data = callback_query.data

    # Переход в меню кланов (служебная кнопка)
    if data == "clan_menu":
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛡 Мой клан", callback_data="🛡 Мой клан")],
            [InlineKeyboardButton("🔙 В главное меню", callback_data="🔙 В главное меню")]
        ])
        await callback_query.message.edit_text("🛡 **Меню Кланов:**", reply_markup=markup)
        return

    # Нажатие на кнопку карты в бою
    if data.startswith("hit|"):
        parts = data.split("|")
        chat_id = int(parts[1])
        msg_id = int(parts[2])
        real_cb_data = parts[3].encode()

        try:
            await userbot.request_callback_answer(
                chat_id=chat_id,
                message_id=msg_id,
                callback_data=real_cb_data
            )
            await callback_query.answer("✅ Ход сделан!")
            await callback_query.message.edit_reply_markup(reply_markup=None)
        except Exception as e:
            await callback_query.answer(f"Ошибка: {e}", show_alert=True)
        return

    # ЛЮБАЯ ДРУГАЯ КНОПКА (Арена, Профиль, Мой клан и т.д.)
    # Мы просто отправляем текст кнопки в игру от лица Твинка
    game_text = data
    try:
        await userbot.send_message(GAME_BOT, game_text)
        await callback_query.answer(f"✅ Отправлено: {game_text}")
    except Exception as e:
        await callback_query.answer(f"Ошибка: {e}", show_alert=True)


# --- ЗАПУСК ---
async def main():
    print("Запускаем...")
    await userbot.start()
    await manager_bot.start()
    print("Все работает!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
