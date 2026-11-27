import asyncio
import os
import time
from collections import defaultdict

from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, ReplyKeyboardMarkup,
    InputMediaPhoto, InputMediaVideo, InputMediaAnimation,
    InputMediaAudio, InputMediaDocument,
)

# ================= НАСТРОЙКИ =================
API_ID          = int(os.environ["TELEGRAM_API_ID"])
API_HASH        = os.environ["TELEGRAM_API_HASH"]
SESSION_STRING  = os.environ["SESSION_STRING"]
MANAGER_BOT_TOKEN = os.environ["MANAGER_BOT_TOKEN"]

ADMIN_IDS   = [int(x) for x in os.environ.get("ADMIN_IDS", "5002413408").split(",") if x]
GAME_BOT    = os.environ.get("GAME_BOT", "anicardplaybot")

# анти-флуд: не пересылать из одного чата чаще, чем раз в N секунд
COOLDOWN_SEC = float(os.environ.get("COOLDOWN_SEC", "0.4"))

userbot = Client("ani_helper", api_id=API_ID, api_hash=API_HASH,
                 session_string=SESSION_STRING, in_memory=True)
manager_bot = Client("manager", api_id=API_ID, api_hash=API_HASH,
                     bot_token=MANAGER_BOT_TOKEN, in_memory=True)

_last_seen = {}          # chat_id -> time.time()
_album_buf = defaultdict(list)   # media_group_id -> [(file_id, caption)]
_album_task = {}         # media_group_id -> asyncio.TimerHandle


# ================= ХЕЛПЕРЫ =================
def _is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def _media_file_id(m: Message):
    """Возвращает (метод_send, file_id, is_groupable) для медиа-сообщения."""
    if m.photo:        return "send_photo", m.photo.file_id, True
    if m.video:        return "send_video", m.video.file_id, True
    if m.animation:    return "send_animation", m.animation.file_id, True
    if m.audio:        return "send_audio", m.audio.file_id, False
    if m.voice:        return "send_voice", m.voice.file_id, False
    if m.video_note:   return "send_video_note", m.video_note.file_id, False
    if m.sticker:      return "send_sticker", m.sticker.file_id, False
    if m.document:     return "send_document", m.document.file_id, True
    return None, None, False


def _rebuild_buttons(m: Message):
    """
    Перестраивает кнопки сообщения игры в кликабельные для админа.
    Возвращает (markup, has_interactive).
    """
    rm = m.reply_markup
    if rm is None:
        return None, False

    # ---- INLINE-кнопки ----
    if isinstance(rm, InlineKeyboardMarkup):
        rows = []
        interactive = False
        for row in rm.inline_keyboard:
            admin_row = []
            for b in row:
                if b.callback_data:
                    # интерактивная: нажатие = request_callback_answer на чужом аккаунте
                    admin_row.append(InlineKeyboardButton(
                        b.text,
                        callback_data=f"hit|{m.chat.id}|{m.id}|{b.callback_data}"
                    ))
                    interactive = True
                elif b.url:
                    admin_row.append(InlineKeyboardButton(
                        f"🔗 {b.text}", callback_data=f"url|{b.url}"))
                elif b.web_app or b.game:
                    admin_row.append(InlineKeyboardButton(
                        f"🌐 {b.text}", callback_data="noop|web_app"))
                elif b.switch_inline_query is not None:
                    admin_row.append(InlineKeyboardButton(
                        f"↩️ {b.text}", callback_data="noop|switch"))
                elif b.request_contact:
                    admin_row.append(InlineKeyboardButton(
                        f"📇 {b.text}", callback_data=f"reply|contact|{m.chat.id}|{m.id}"))
                    interactive = True
                elif b.request_location:
                    admin_row.append(InlineKeyboardButton(
                        f"📍 {b.text}", callback_data=f"reply|location|{m.chat.id}|{m.id}"))
                    interactive = True
                elif b.request_poll:
                    admin_row.append(InlineKeyboardButton(
                        f"🗳 {b.text}", callback_data="noop|poll"))
                else:
                    admin_row.append(InlineKeyboardButton(
                        b.text, callback_data="noop|unknown"))
            rows.append(admin_row)
        return InlineKeyboardMarkup(rows), interactive

    # ---- REPLY-кнопки (нижнее меню) ----
    if isinstance(rm, ReplyKeyboardMarkup):
        rows = []
        for row in rm.keyboard:
            admin_row = []
            for b in row:
                if b.request_contact:
                    admin_row.append(InlineKeyboardButton(
                        f"📇 {b.text}", callback_data=f"reply|contact|{m.chat.id}|{m.id}"))
                elif b.request_location:
                    admin_row.append(InlineKeyboardButton(
                        f"📍 {b.text}", callback_data=f"reply|location|{m.chat.id}|{m.id}"))
                elif b.request_poll:
                    admin_row.append(InlineKeyboardButton(
                        f"🗳 {b.text}", callback_data="noop|poll"))
                else:
                    # текстовая reply-кнопка: при нажатии отправим её текст в игру
                    admin_row.append(InlineKeyboardButton(
                        b.text, callback_data=f"reply|text|{m.chat.id}|{m.id}|{b.text}"))
            rows.append(admin_row)
        return InlineKeyboardMarkup(rows), True

    return None, False


async def _send_content(target: int, m: Message, text: str, markup):
    """Отправляет контент сообщения m в чат target, сохранив медиа."""
    method, file_id, _ = _media_file_id(m)

    if method:
        fn = getattr(userbot, method)
        kwargs = {"chat_id": target, "file_id" if method in ("send_photo",) else "media": file_id}
        # pyrogram использует name=... для file_id в send_*; универсально:
        try:
            if method == "send_photo":
                await fn(chat_id=target, photo=file_id, caption=text or None,
                         reply_markup=markup, parse_mode=None)
            elif method == "send_video":
                await fn(chat_id=target, video=file_id, caption=text or None,
                         reply_markup=markup, parse_mode=None)
            elif method == "send_animation":
                await fn(chat_id=target, animation=file_id, caption=text or None,
                         reply_markup=markup, parse_mode=None)
            elif method == "send_audio":
                await fn(chat_id=target, audio=file_id, caption=text or None,
                         reply_markup=markup, parse_mode=None)
            elif method == "send_voice":
                await fn(chat_id=target, voice=file_id, reply_markup=markup)
            elif method == "send_video_note":
                await fn(chat_id=target, video_note=file_id, reply_markup=markup)
            elif method == "send_sticker":
                await fn(chat_id=target, sticker=file_id, reply_markup=markup)
            elif method == "send_document":
                await fn(chat_id=target, document=file_id, caption=text or None,
                         reply_markup=markup, parse_mode=None)
        except Exception as e:
            print(f"[send_content] {method}: {e}")
            await userbot.send_message(target, text or "⚠️ медиа не переслано",
                                       reply_markup=markup, parse_mode=None)
        return

    # без медиа — обычный текст / опрос / контакт / локация / dice
    try:
        if m.poll:
            await userbot.send_message(target, text or "🗳 Опрос", reply_markup=markup, parse_mode=None)
        elif m.contact:
            await userbot.send_message(target, text or "📇 Контакт", reply_markup=markup, parse_mode=None)
        elif m.location:
            await userbot.send_message(target, text or "📍 Геолокация", reply_markup=markup, parse_mode=None)
        elif m.dice:
            await userbot.send_message(target, text or "🎲", reply_markup=markup, parse_mode=None)
        else:
            await userbot.send_message(target, text or "*(пусто)*",
                                       reply_markup=markup, parse_mode=None)
    except Exception as e:
        print(f"[send_content] text: {e}")


async def _flush_album(group_id: str):
    """Отправляет собранный альбом одним сообщением-группой."""
    items = _album_buf.pop(group_id, [])
    _album_task.pop(group_id, None)
    if not items:
        return
    media = []
    for file_id, cap in items:
        media.append(InputMediaPhoto(media=file_id, caption=cap or None))
    for admin in ADMIN_IDS:
        try:
            await userbot.send_media_group(chat_id=admin, media=media)
        except Exception as e:
            print(f"[album] {e}")
            for file_id, cap in items:
                try:
                    await userbot.send_photo(admin, photo=file_id, caption=cap)
                except Exception:
                    pass


async def relay(m: Message):
    """Главная пересылка одного сообщения игры."""
    now = time.time()
    if now - _last_seen.get(m.chat.id, 0) < COOLDOWN_SEC and not m.media_group_id:
        #edited-спам: пропускаем, если слишком часто
        return
    _last_seen[m.chat.id] = now

    markup, interactive = _rebuild_buttons(m)
    text = m.text or m.caption or ""

    # ---- АЛЬБОМ (media_group) ----
    if m.media_group_id and m.photo:
        _album_buf[m.media_group_id].append((m.photo.file_id, m.caption))
        # перезапускаем таймер
        old = _album_task.get(m.media_group_id)
        if old:
            old.cancel()
        loop = asyncio.get_running_loop()
        _album_task[m.media_group_id] = loop.call_later(
            0.8, lambda: asyncio.create_task(_flush_album(m.media_group_id))
        )
        return

    # ---- Без кнопок: точная копия (сохраняет медиа + форматирование) ----
    if m.reply_markup is None:
        for admin in ADMIN_IDS:
            try:
                await userbot.copy_message(admin, from_chat_id=m.chat.id, message_id=m.id)
            except Exception as e:
                print(f"[copy] {e}")
                await _send_content(admin, m, text, None)
        return

    # ---- С кнопками: реконструкция ----
    header = "🎮 " if not text else ""
    body = (text or "*(без текста)*")
    for admin in ADMIN_IDS:
        await _send_content(admin, m, header + body, markup)


# ================= 1. ЛОВИМ ВСЁ В ИГРЕ =================
@userbot.on_message(filters.user(GAME_BOT))
async def on_game_msg(client: Client, m: Message):
    await relay(m)

@userbot.on_edited_message(filters.user(GAME_BOT))
async def on_game_edit(client: Client, m: Message):
    await relay(m)


# ================= 2. МЕНЮ АДМИНА =================
@manager_bot.on_message(filters.command("start") & filters.user(ADMIN_IDS))
async def cmd_start(c, m: Message):
    await m.reply("👋 Привет! Используй /menu для навигации или просто пиши текст — он уйдёт в игру.")

@manager_bot.on_message(filters.command("menu") & filters.user(ADMIN_IDS))
async def cmd_menu(c, m: Message):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏟 Арена", callback_data="🏟 Арена"),
         InlineKeyboardButton("🛡 Кланы", callback_data="🛡 Кланы")],
        [InlineKeyboardButton("📜 Меню", callback_data="📜 Меню")],
    ])
    await m.reply("Куда отправить действие:", reply_markup=kb)

@manager_bot.on_message(filters.command("status") & filters.user(ADMIN_IDS))
async def cmd_status(c, m: Message):
    await m.reply(f"✅ Юзербот: {await userbot.get_me().username}\n"
                  f"🎮 Игра: {GAME_BOT}\n"
                  f"👤 Админов: {len(ADMIN_IDS)}")


# ================= 3. НАЖАТИЯ КНОПОК =================
@manager_bot.on_callback_query()
async def on_callback(c, q: CallbackQuery):
    if not _is_admin(q.from_user.id):
        return await q.answer("⛔ Нет доступа", show_alert=True)

    data = q.data or ""

    # --- inline-callback: нажимаем кнопку НА ЧУЖОМ аккаунте ---
    if data.startswith("hit|"):
        try:
            _, chat_id, msg_id, cb = data.split("|", 3)
            await userbot.request_callback_answer(
                chat_id=int(chat_id), message_id=int(msg_id), callback_data=cb
            )
            await q.answer("✅ Ход отправлен в игру")
        except Exception as e:
            await q.answer(f"❌ {e}", show_alert=True)
        return

    # --- reply-кнопки: имитируем нажатие нижнего меню ---
    if data.startswith("reply|"):
        parts = data.split("|")
        kind = parts[1]
        try:
            if kind == "text":
                chat_id = int(parts[2]); msg_id = int(parts[3]); txt = "|".join(parts[4:])
                await userbot.send_message(GAME_BOT, txt)
                await q.answer("✅ Отправлено в игру")
            elif kind == "contact":
                # фиктивный контакт (имя = текст кнопки). Игра обычно принимает любой контакт.
                await userbot.send_contact(
                    GAME_BOT, phone_number="0000000000",
                    first_name="Twin", last_name="Manager"
                )
                await q.answer("✅ Контакт отправлен")
            elif kind == "location":
                await userbot.send_location(GAME_BOT, latitude=0.0, longitude=0.0)
                await q.answer("✅ Геолокация отправлена")
            else:
                await q.answer("⚠️ Неизвестный reply", show_alert=True)
        except Exception as e:
            await q.answer(f"❌ {e}", show_alert=True)
        return

    # --- ссылка: просто показываем ---
    if data.startswith("url|"):
        url = data[4:]
        await q.answer("🔗 Ссылка в чате")
        for admin in ADMIN_IDS:
            await userbot.send_message(admin, f"🔗 {url}")
        return

    # --- некликабельные типы ---
    if data.startswith("noop|"):
        await q.answer("⚠️ Этот тип кнопок нельзя нажать за соклана", show_alert=True)
        return

    # --- обычные кнопки меню (🏟 Арена и т.п.): отправляем как текст в игру ---
    try:
        await userbot.send_message(GAME_BOT, data)
        await q.answer(f"✅ → {data}")
    except Exception as e:
        await q.answer(f"❌ {e}", show_alert=True)


# ================= 4. ТЕКСТ АДМИНА → В ИГРУ =================
@manager_bot.on_message(filters.user(ADMIN_IDS) & filters.text & ~filters.command(["start","menu","status"]))
async def on_text(c, m: Message):
    try:
        await userbot.send_message(GAME_BOT, m.text)
        await m.reply(f"✅ Отправлено в игру: {m.text}")
    except Exception as e:
        await m.reply(f"❌ {e}")


# ================= ЗАПУСК =================
async def main():
    await userbot.start()
    await manager_bot.start()
    me = await userbot.get_me()
    print(f"✅ Юзербот: @{me.username} | Игра: {GAME_BOT} | Админы: {ADMIN_IDS}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
