import asyncio
import logging
import sqlite3
import uuid
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===== Логирование =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ===== Конфиг =====
# ⚠️ Рекомендуется вынести TOKEN и ADMIN_ID в .env файл:
#   pip install python-dotenv
#   from dotenv import load_dotenv; import os; load_dotenv()
#   TOKEN = os.getenv("TOKEN")
#   ADMIN_ID = int(os.getenv("ADMIN_ID"))
TOKEN = "8749552858:AAG4YNxHBEDzhlMy9-ibLg958jKIviooN_s"
ADMIN_ID = 568518218
POST_CHANNEL = -1002302377431

bot = Bot(token=TOKEN)
dp = Dispatcher(bot=bot)

# ===== Временные состояния (в памяти) =====
adding_state = {}
deleting_state = {}
broadcast_state = {}
filters_state = {}

# ===== База данных SQLite =====
DB_PATH = "shop.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                photo TEXT,
                price TEXT,
                number TEXT,
                vk TEXT,
                albums TEXT DEFAULT '',
                channel_message_id INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS filters (
                user_id INTEGER PRIMARY KEY,
                min_price INTEGER,
                max_price INTEGER
            )
        """)
    logger.info("База данных инициализирована.")

# ----- Аккаунты -----

def db_get_all_accounts() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT id, photo, price, number, vk, albums, channel_message_id FROM accounts").fetchall()
    result = {}
    for row in rows:
        acc_id, photo, price, number, vk, albums_raw, channel_message_id = row
        albums = [a for a in albums_raw.split("\n") if a] if albums_raw else []
        result[acc_id] = {"photo": photo, "price": price, "number": number, "vk": vk, "albums": albums, "channel_message_id": channel_message_id}
    return result

def db_add_account(photo, price, number, vk, albums: list, channel_message_id: int = None) -> str:
    acc_id = str(uuid.uuid4())[:8]
    albums_raw = "\n".join(albums)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO accounts (id, photo, price, number, vk, albums, channel_message_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (acc_id, photo, price, number, vk, albums_raw, channel_message_id)
        )
    logger.info(f"Добавлен аккаунт id={acc_id}, number={number}")
    return acc_id

def db_get_channel_message_ids_by_number(number: str) -> list[int]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT channel_message_id FROM accounts WHERE number = ? AND channel_message_id IS NOT NULL", (number,)
        ).fetchall()
    return [r[0] for r in rows]

def db_delete_accounts_by_number(number: str) -> int:
    with get_conn() as conn:
        cursor = conn.execute("DELETE FROM accounts WHERE number = ?", (number,))
        deleted = cursor.rowcount
    logger.info(f"Удалено аккаунтов с number={number}: {deleted}")
    return deleted

def db_get_account(acc_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, photo, price, number, vk, albums, channel_message_id FROM accounts WHERE id = ?", (acc_id,)
        ).fetchone()
    if not row:
        return None
    acc_id, photo, price, number, vk, albums_raw, channel_message_id = row
    albums = [a for a in albums_raw.split("\n") if a] if albums_raw else []
    return {"photo": photo, "price": price, "number": number, "vk": vk, "albums": albums, "channel_message_id": channel_message_id}

# ----- Подписчики -----

def db_add_subscriber(user_id: int):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO subscribers (user_id) VALUES (?)", (user_id,))

def db_get_subscribers() -> list[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id FROM subscribers").fetchall()
    return [r[0] for r in rows]

# ----- Фильтры -----

def db_get_filter(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT min_price, max_price FROM filters WHERE user_id = ?", (user_id,)
        ).fetchone()
    return {"min": row[0], "max": row[1]} if row else None

def db_set_filter(user_id: int, min_price: int, max_price: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO filters (user_id, min_price, max_price) VALUES (?, ?, ?)",
            (user_id, min_price, max_price)
        )
    logger.info(f"Фильтр сохранён для user_id={user_id}: {min_price}-{max_price}")

def db_delete_filter(user_id: int) -> bool:
    with get_conn() as conn:
        cursor = conn.execute("DELETE FROM filters WHERE user_id = ?", (user_id,))
        return cursor.rowcount > 0

def db_get_all_filters() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id, min_price, max_price FROM filters").fetchall()
    return {r[0]: {"min": r[1], "max": r[2]} for r in rows}

# ===== Клавиатуры =====

def nav_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
    kb.add(InlineKeyboardButton("Наши отзывы", url="https://t.me/Dvornov_Otziv"))
    return kb

def main_menu_keyboard(user_id: int):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🛒 Открыть маркет", web_app={"url": "https://sheraron2004-spec.github.io/dvornov-market/"}))
    kb.add(InlineKeyboardButton("💎 Продать свой аккаунт", url="https://t.me/DvornovNikitos"))
    kb.add(InlineKeyboardButton("⭐ Наши отзывы", url="https://t.me/Dvornov_Otziv"))
    kb.add(InlineKeyboardButton("📞 Написать Дворнову", url="https://t.me/DvornovNikitos"))
    if user_id == ADMIN_ID:
        kb.add(InlineKeyboardButton("⚙️ Админ панель", callback_data="admin_panel"))
    return kb

# ===== Старт / главное меню =====

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    db_add_subscriber(message.from_user.id)
    kb = main_menu_keyboard(message.from_user.id)
    text = (
        "⚽ *eFootball Bazar Shop* ⚽\n\n"
        "Здесь ты можешь:\n"
        "💰 Купить или обменять аккаунт\n"
        "💎 Продать свой аккаунт Никите Дворнову\n"
        "📸 Смотреть фулл-скрины и отзывы\n\n"
        "🤍 Надёжность и удобство — всё в одном боте."
    )
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "main_menu")
async def go_main_menu(callback: types.CallbackQuery):
    adding_state.pop(callback.from_user.id, None)
    deleting_state.pop(callback.from_user.id, None)
    broadcast_state.pop(callback.from_user.id, None)
    filters_state.pop(callback.from_user.id, None)

    kb = main_menu_keyboard(callback.from_user.id)
    try:
        await callback.message.edit_text("🏠 Главное меню", reply_markup=kb)
    except Exception:
        await callback.message.answer("🏠 Главное меню", reply_markup=kb)
    await callback.answer()

# ===== Навигация назад в процессе добавления =====

@dp.callback_query_handler(lambda c: c.data == "back_step")
async def go_back_step(callback: types.CallbackQuery):
    if callback.from_user.id in adding_state:
        state = adding_state[callback.from_user.id]
        step = state.get("step")
        if step == "price":
            state["step"] = "photo"
            await callback.message.answer("📸 Отправь фото аккаунта:", reply_markup=nav_keyboard())
        elif step == "number":
            state["step"] = "price"
            await callback.message.answer("💰 Укажи цену (только число):", reply_markup=nav_keyboard())
        elif step == "vk":
            state["step"] = "number"
            await callback.message.answer("🔢 Укажи число аккаунта:", reply_markup=nav_keyboard())
        elif step == "album":
            state["step"] = "vk"
            await callback.message.answer("🔗 Укажи ссылку на VK магазин (или 'нет'):", reply_markup=nav_keyboard())
    await callback.answer()

# ===== Админ панель =====

@dp.callback_query_handler(lambda c: c.data == "admin_panel" and c.from_user.id == ADMIN_ID)
async def admin_panel(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Добавить аккаунт", callback_data="add_account"))
    kb.add(InlineKeyboardButton("❌ Удалить аккаунт", callback_data="delete_account"))
    kb.add(InlineKeyboardButton("📣 Рассылка подписчикам", callback_data="broadcast"))
    kb.add(InlineKeyboardButton("🏠 Меню", callback_data="main_menu"))
    kb.add(InlineKeyboardButton("Наши отзывы", url="https://t.me/Dvornov_Otziv"))
    await callback.message.answer("⚙️ Админ панель", reply_markup=kb)
    await callback.answer()

# ===== Добавление аккаунта (админ) =====

@dp.callback_query_handler(lambda c: c.data == "add_account" and c.from_user.id == ADMIN_ID)
async def add_account_start(callback: types.CallbackQuery):
    adding_state[callback.from_user.id] = {"step": "photo", "albums": []}
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
    kb.add(InlineKeyboardButton("Наши отзывы", url="https://t.me/Dvornov_Otziv"))
    await callback.message.answer("📸 Отправь фото аккаунта:", reply_markup=kb)
    await callback.answer()

@dp.message_handler(
    lambda m: m.from_user.id == ADMIN_ID and m.from_user.id in adding_state,
    content_types=["photo"]
)
async def handle_photo(message: types.Message):
    state = adding_state[message.from_user.id]
    if state.get("step") == "photo":
        state["photo"] = message.photo[-1].file_id
        state["step"] = "price"
        await message.answer("💰 Укажи цену (только число, без валюты):", reply_markup=nav_keyboard())

@dp.message_handler(
    lambda m: m.from_user.id == ADMIN_ID and m.from_user.id in adding_state,
    content_types=["text"]
)
async def process_add(message: types.Message):
    state = adding_state[message.from_user.id]

    if state.get("step") == "price":
        state["price"] = message.text.strip()
        state["step"] = "number"
        return await message.answer("🔢 Укажи число аккаунта:", reply_markup=nav_keyboard())

    elif state.get("step") == "number":
        state["number"] = message.text.strip()
        state["step"] = "vk"
        return await message.answer("🔗 Укажи ссылку на VK магазин (или напиши 'нет'):", reply_markup=nav_keyboard())

    elif state.get("step") == "vk":
        state["vk"] = message.text.strip()
        state["step"] = "album"
        return await message.answer("📸 Скинь ссылку на альбом (или 'нет'):", reply_markup=nav_keyboard())

    elif state.get("step") == "album":
        if message.text.lower().strip() != "нет":
            state["albums"].append(message.text.strip())
            return await message.answer("✅ Добавлено! Ещё альбом? Если нет — напиши 'нет'.", reply_markup=nav_keyboard())
        else:
            acc_id = db_add_account(
                photo=state.get("photo"),
                price=state.get("price"),
                number=state.get("number"),
                vk=state.get("vk", ""),
                albums=state.get("albums", [])
            )

            # Пост в канал
            text = f"""🔥{state.get('price')}🔥 

[{state.get('number')}] - Число аккаунта (говорите его когда хотите купить либо обменять)

{state.get('vk')}

🤍Для покупки - @DvornovNikitos🤍

Продажа ✅
Обмен✅
Обмен с моей доплатой ✅
Обмен с вашей доплатой ✅
Обмен на нфт подарок ТГ + доп✅

Если у тебя Спамблок пиши в группу, я тебе напишу - @dvornov_spam

Мои отзывы - @Dvornov_Otziv

‼фулл скрины в моем боте @Efootball_dvornovbot

Хочешь переслать/сфоткать аккаунт? Заходи в комментарии и там сделай что хочешь.
"""
            try:
                sent_msg = await bot.send_photo(POST_CHANNEL, photo=state.get("photo"), caption=text)
                channel_message_id = sent_msg.message_id
                # Обновляем запись с ID поста в канале
                with get_conn() as conn:
                    conn.execute(
                        "UPDATE accounts SET channel_message_id = ? WHERE id = ?",
                        (channel_message_id, acc_id)
                    )
                await message.answer("✅ Аккаунт добавлен и пост опубликован!", reply_markup=nav_keyboard())
            except Exception as e:
                logger.warning(f"Не удалось отправить пост в канал: {e}")
                await message.answer(f"⚠️ Аккаунт сохранён, но пост не удалось отправить: {e}", reply_markup=nav_keyboard())

            # Уведомления подписчикам с учётом фильтров
            notify_text_general = f"🔔 Добавлен новый аккаунт!\n\n💰 {state.get('price')}\n🔢 {state.get('number')}"
            kb_notify = InlineKeyboardMarkup()
            kb_notify.add(InlineKeyboardButton("Посмотреть аккаунты", callback_data="show_accounts"))
            kb_notify.add(InlineKeyboardButton("Наши отзывы", url="https://t.me/Dvornov_Otziv"))

            try:
                price_int = int(''.join(ch for ch in str(state.get("price")) if ch.isdigit()))
            except Exception:
                price_int = None

            all_filters = db_get_all_filters()
            subscribers = db_get_subscribers()

            for user_id in subscribers:
                try:
                    user_filter = all_filters.get(user_id)
                    if user_filter and price_int is not None:
                        if user_filter["min"] <= price_int <= user_filter["max"]:
                            text_f = f"🔔 Новый аккаунт по вашему фильтру!\n\n💰 {state.get('price')}\n🔢 {state.get('number')}"
                            if state.get("photo"):
                                await bot.send_photo(user_id, photo=state.get("photo"), caption=text_f, reply_markup=kb_notify)
                            else:
                                await bot.send_message(user_id, text_f, reply_markup=kb_notify)
                            await asyncio.sleep(0.05)
                            continue
                    if state.get("photo"):
                        await bot.send_photo(user_id, photo=state.get("photo"), caption=notify_text_general, reply_markup=kb_notify)
                    else:
                        await bot.send_message(user_id, notify_text_general, reply_markup=kb_notify)
                    await asyncio.sleep(0.05)
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление user_id={user_id}: {e}")
                    continue

            adding_state.pop(message.from_user.id, None)

# ===== Удаление аккаунта (админ) =====

@dp.callback_query_handler(lambda c: c.data == "delete_account" and c.from_user.id == ADMIN_ID)
async def delete_account_start(callback: types.CallbackQuery):
    deleting_state[callback.from_user.id] = True
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
    await callback.message.answer("❌ Введи число аккаунта для удаления (все совпадения будут удалены):", reply_markup=kb)
    await callback.answer()

@dp.message_handler(
    lambda m: m.from_user.id == ADMIN_ID and m.from_user.id in deleting_state,
    content_types=["text"]
)
async def process_delete(message: types.Message):
    number = message.text.strip()

    # Получаем ID постов в канале до удаления
    channel_msg_ids = db_get_channel_message_ids_by_number(number)
    deleted = db_delete_accounts_by_number(number)

    if deleted == 0:
        await message.answer("❌ Аккаунт с таким числом не найден.", reply_markup=main_menu_keyboard(message.from_user.id))
    else:
        # Удаляем посты из канала
        deleted_from_channel = 0
        for msg_id in channel_msg_ids:
            try:
                await bot.delete_message(POST_CHANNEL, msg_id)
                deleted_from_channel += 1
            except Exception as e:
                logger.warning(f"Не удалось удалить пост {msg_id} из канала: {e}")

        channel_info = f"\n?? Удалено постов из канала: {deleted_from_channel}" if channel_msg_ids else "\n⚠️ Посты в канале не найдены."
        await message.answer(
            f"✅ Удалено {deleted} аккаунт(ов) с числом {number}.{channel_info}",
            reply_markup=main_menu_keyboard(message.from_user.id)
        )

    deleting_state.pop(message.from_user.id, None)

# ===== Рассылка (админ) =====

@dp.callback_query_handler(lambda c: c.data == "broadcast" and c.from_user.id == ADMIN_ID)
async def start_broadcast(callback: types.CallbackQuery):
    broadcast_state[callback.from_user.id] = True
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
    await callback.message.answer("📣 Введи текст рассылки. Я отправлю его всем подписчикам.", reply_markup=kb)
    await callback.answer()

@dp.message_handler(
    lambda m: m.from_user.id == ADMIN_ID and m.from_user.id in broadcast_state,
    content_types=["text"]
)
async def process_broadcast(message: types.Message):
    text = message.text.strip()
    if not text:
        await message.answer("⚠️ Текст пустой. Отмена.", reply_markup=main_menu_keyboard(message.from_user.id))
        broadcast_state.pop(message.from_user.id, None)
        return

    sent = 0
    failed = 0
    kb_b = InlineKeyboardMarkup()
    kb_b.add(InlineKeyboardButton("Посмотреть аккаунты", callback_data="show_accounts"))
    kb_b.add(InlineKeyboardButton("Наши отзывы", url="https://t.me/Dvornov_Otziv"))

    for user_id in db_get_subscribers():
        try:
            await bot.send_message(user_id, text, reply_markup=kb_b)
            sent += 1
            await asyncio.sleep(0.05)  # защита от flood-ban
        except Exception as e:
            logger.warning(f"Рассылка: не удалось отправить user_id={user_id}: {e}")
            failed += 1

    await message.answer(
        f"✅ Рассылка завершена. Отправлено: {sent}. Ошибок: {failed}.",
        reply_markup=main_menu_keyboard(message.from_user.id)
    )
    broadcast_state.pop(message.from_user.id, None)

# ===== Фильтры =====

@dp.callback_query_handler(lambda c: c.data == "filters")
async def show_filters(callback: types.CallbackQuery):
    db_add_subscriber(callback.from_user.id)
    flt = db_get_filter(callback.from_user.id)
    kb = InlineKeyboardMarkup()
    if flt:
        kb.add(InlineKeyboardButton("✏️ Редактировать", callback_data="edit_filter"))
        kb.add(InlineKeyboardButton("🗑 Удалить", callback_data="delete_filter"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
        await callback.message.answer(f"📊 Ваш фильтр: от {flt['min']} до {flt['max']}", reply_markup=kb)
    else:
        kb.add(InlineKeyboardButton("➕ Создать фильтр", callback_data="create_filter"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
        await callback.message.answer(
            "📊 У вас пока нет фильтра.\n\nФильтр позволяет получать уведомления только об аккаунтах в нужном диапазоне цен.",
            reply_markup=kb
        )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data in ["create_filter", "edit_filter"])
async def ask_filter(callback: types.CallbackQuery):
    filters_state[callback.from_user.id] = "creating" if callback.data == "create_filter" else "editing"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
    await callback.message.answer("✍️ Напишите диапазон цен в формате `200-500` (только числа).", reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.message_handler(lambda m: m.from_user.id in filters_state, content_types=["text"])
async def set_filter(message: types.Message):
    text = message.text.strip()
    try:
        parts = text.split("-")
        if len(parts) != 2:
            raise ValueError("Неверный формат")
        min_price = int(''.join(ch for ch in parts[0] if ch.isdigit()))
        max_price = int(''.join(ch for ch in parts[1] if ch.isdigit()))
        if min_price > max_price:
            min_price, max_price = max_price, min_price
        db_set_filter(message.from_user.id, min_price, max_price)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
        await message.answer(f"✅ Фильтр сохранён: от {min_price} до {max_price}.", reply_markup=kb)
    except Exception:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
        await message.answer("⚠️ Неверный формат. Напишите диапазон в виде: 200-500", reply_markup=kb)
    finally:
        filters_state.pop(message.from_user.id, None)

@dp.callback_query_handler(lambda c: c.data == "delete_filter")
async def delete_filter(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Создать фильтр", callback_data="create_filter"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
    if db_delete_filter(callback.from_user.id):
        await callback.message.answer("🗑 Фильтр удалён.", reply_markup=kb)
    else:
        await callback.message.answer("⚠️ У вас нет фильтра.", reply_markup=kb)
    await callback.answer()

# ===== Продать свой аккаунт =====

@dp.callback_query_handler(lambda c: c.data == "sell_account")
async def sell_account(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔗 Написать Дворнову", url="https://t.me/DvornovNikitos"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
    await callback.message.answer(
        "💎 *Хотите продать свой аккаунт?*\n\n"
        "Никита Дворнов может купить ваш аккаунт.\n\n"
        "✍️ Пишите только кратко: фото + цена.\n\n"
        "Все детали обсуждаются лично в переписке с Никитой.",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()

# ===== Показ аккаунтов =====

@dp.callback_query_handler(lambda c: c.data == "show_accounts")
async def show_accounts(callback: types.CallbackQuery):
    db_add_subscriber(callback.from_user.id)
    accounts = db_get_all_accounts()
    if not accounts:
        await callback.message.answer("Пока нет аккаунтов.", reply_markup=main_menu_keyboard(callback.from_user.id))
        await callback.answer()
        return

    for acc_id, acc in accounts.items():
        caption = f"💰 {acc.get('price')}\n🔢 {acc.get('number')}"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔴 Купить/Обменять", url="https://t.me/DvornovNikitos"))
        kb.add(InlineKeyboardButton("Посмотреть фулл‑скрины", callback_data=f"albums_{acc_id}"))
        kb.add(InlineKeyboardButton("Наши отзывы", url="https://t.me/Dvornov_Otziv"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))

        photo = acc.get("photo")
        try:
            if photo:
                await callback.message.answer_photo(photo, caption=caption, reply_markup=kb)
            else:
                await callback.message.answer(caption, reply_markup=kb)
        except Exception as e:
            logger.warning(f"Ошибка при показе аккаунта {acc_id}: {e}")
            await callback.message.answer(caption, reply_markup=kb)

    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("albums_"))
async def show_albums(callback: types.CallbackQuery):
    acc_id = callback.data.split("_", 1)[1]
    acc = db_get_account(acc_id)
    if not acc:
        await callback.answer("Аккаунт не найден.", show_alert=True)
        return

    for link in acc.get("albums", []):
        await callback.message.answer(f"📸 Альбом: {link}")

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"back_{acc_id}"))
    kb.add(InlineKeyboardButton("Наши отзывы", url="https://t.me/Dvornov_Otziv"))
    kb.add(InlineKeyboardButton("🏠 Меню", callback_data="main_menu"))
    await callback.message.answer("Выше ссылки на альбомы 👆", reply_markup=kb)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("back_"))
async def back_to_account(callback: types.CallbackQuery):
    acc_id = callback.data.split("_", 1)[1]
    acc = db_get_account(acc_id)
    if not acc:
        await callback.answer("Аккаунт не найден.", show_alert=True)
        return

    caption = f"💰 {acc.get('price')}\n🔢 {acc.get('number')}"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔴 Купить/Обменять", url="https://t.me/DvornovNikitos"))
    kb.add(InlineKeyboardButton("Посмотреть фулл‑скрины", callback_data=f"albums_{acc_id}"))
    kb.add(InlineKeyboardButton("Наши отзывы", url="https://t.me/Dvornov_Otziv"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))

    photo = acc.get("photo")
    try:
        if photo:
            await callback.message.answer_photo(photo, caption=caption, reply_markup=kb)
        else:
            await callback.message.answer(caption, reply_markup=kb)
    except Exception as e:
        logger.warning(f"Ошибка при возврате к аккаунту {acc_id}: {e}")
        await callback.message.answer(caption, reply_markup=kb)

    await callback.answer()

# ===== Запуск =====

async def main():
    init_db()
    logger.info("Бот запущен.")
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
