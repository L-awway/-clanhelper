import asyncio
import os
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetBotCallbackAnswerRequest

# --- НАСТРОЙКИ ---
API_ID = int(os.environ.get("TELEGRAM_API_ID"))
API_HASH = os.environ.get("TELEGRAM_API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")
MANAGER_BOT_TOKEN = os.environ.get("MANAGER_BOT_TOKEN")

ADMIN_IDS = [5002413408]  # Ваш ID
GAME_BOT = "anicardplaybot"

# --- КЛИЕНТЫ ---
print("1. Переменные загружены. Инициализация клиентов...")

# Юзербот (сидит в Твинке). Используем сессию, которую выдал Tobigram
userbot = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# Бот-менеджер (с ним вы общаетесь)
manager_bot = TelegramClient('manager_session', API_ID, API_HASH).start(bot_token=MANAGER_BOT_TOKEN)

# Чтобы знать, какое сообщение в игре к какому сообщению у вас в чате привязано
active_battles = {}

# --- ЛОВИМ ИГРУ В ЮЗЕРБОТЕ ---
@userbot.on(events.NewMessage(from_users=GAME_BOT))
@userbot.on(events.MessageEdited(from_users=GAME_BOT))
async def game_bot_handler(event):
    message = event.message
    print(f"Поймано сообщение от AniCard: {message.id}")
    
    text = f"🎮 **Событие в игре (Твинк):**\n\n{message.text}"
    buttons = []
    
    # Если есть кнопки — переносим их
    if message.buttons:
        for row in message.buttons:
            btn_row = []
            for btn in row:
                # Сохраняем данные кнопки и ID сообщения
                btn_row.append(Button.inline(
                    text=btn.text, 
                    data=f"hit|{message.id}|{btn.data.hex() if btn.data else ''}"
                ))
            buttons.append(btn_row)
    
    # Отправляем инфу всем админам
    for admin_id in ADMIN_IDS:
        try:
            sent_msg = await manager_bot.send_message(
                entity=admin_id,
                message=text,
                buttons=buttons if buttons else None
            )
            # Запоминаем, какое сообщение в игре соответствует этому сообщению в боте
            active_battles[sent_msg.id] = message.id
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")

# --- ОБЩЕНИЕ С ВАМИ (Бот-Менеджер) ---
@manager_bot.on(events.NewMessage(pattern='/start', from_users=ADMIN_IDS))
async def start_handler(event):
    await event.reply(
        "👋 **Привет, Админ!**\n\n"
        "Я подключен к аккаунту Твинка.\n"
        "Когда начнется бой, жми кнопки прямо здесь — Твинк сделает ход."
    )

# --- ЛОВИМ ВАШИ НАЖАТИЯ НА КНОПКИ ---
@manager_bot.on(events.CallbackQuery)
async def callback_handler(event):
    if event.sender_id not in ADMIN_IDS:
        return await event.answer("Нет доступа")

    data = event.data.decode('utf-8').split("|")
    if data[0] == "hit":
        game_msg_id = int(data[1])
        real_cb_data = bytes.fromhex(data[2]) if data[2] else b""

        try:
            # Твинк нажимает кнопку в игре
            await userbot(GetBotCallbackAnswerRequest(
                peer=GAME_BOT,
                msg_id=game_msg_id,
                data=real_cb_data
            ))
            await event.answer("✅ Ход сделан от лица Твинка!")
            await event.delete() # Удаляем сообщение из чата с ботом
        except Exception as e:
            await event.answer(f"Ошибка: {e}", show_alert=True)

# --- ЗАПУСК ---
async def main():
    print("Запускаем Юзербота...")
    await userbot.start()
    print("Юзербот успешно запущен!")
    
    print("Запускаем Бота-менеджера...")
    print("Всё работает! Ждем боя.")
    
    await asyncio.gather(
        userbot.run_until_disconnected(),
        manager_bot.run_until_disconnected()
    )

if __name__ == "__main__":
    print("=== СТАРТ БОТА ===")
    asyncio.run(main())
