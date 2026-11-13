import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import Message

# Берем данные из переменных окружения Bothost
API_ID = int(os.environ.get("TELEGRAM_API_ID"))
API_HASH = os.environ.get("TELEGRAM_API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

# Инициализируем клиента
app = Client(
    name="ani_helper",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)

# Слушаем сообщения ТОЛЬКО от бота AniCard
# ВАЖНО: Замените "anicardplaybot" на ТОЧНЫЙ юзернейм бота, если он другой
@app.on_message(filters.user("anicardplaybot"))
async def anicard_handler(client: Client, message: Message):
    print("\n" + "="*50)
    print(f"Пришло сообщение (ID: {message.id})")
    print("-" * 50)
    
    # Выводим текст боя
    if message.text:
        print(message.text)
    
    # Выводим кнопки (карты)
    if message.reply_markup:
        print("-" * 50)
        print("Доступные кнопки:")
        for i, row in enumerate(message.reply_markup.inline_keyboard):
            for j, button in enumerate(row):
                print(f"  [{i}][{j}] '{button.text}'")

async def main():
    print("Бот запущен и слушает AniCard...")
    await app.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
