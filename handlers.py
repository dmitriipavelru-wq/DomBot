import secrets
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from ai_helper import parse_task_with_ai

router = Router()

class FamilyStates(StatesGroup):
    waiting_family_name = State()

class TaskStates(StatesGroup):
    waiting_task_text = State()
    waiting_member_choice = State()
    confirm_ai_parse = State()

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    await db.create_user(user.id, user.first_name)
    existing = await db.get_user(user.id)
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("join_"):
        code = args[1]
        family = await db.get_family_by_code(code)
        if family:
            await db.set_user_family(user.id, family["id"], is_admin=False)
            await message.answer(
                f"🎉 Ты вступил в семью *{family['name']}*!\n\nТеперь тебе будут приходить напоминания.",
                parse_mode="Markdown"
            )
            return
        else:
            await message.answer("❌ Неверная ссылка приглашения.")
            return
    if existing and existing["family_id"]:
        await show_main_menu(message, existing)
    else:
        await message.answer(
            f"👋 Привет, *{user.first_name}*!\n\nЯ *DomBot* — помогаю семье не забывать важное.\n\nСоздай семью или вступи по ссылке от родных:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Создать семью", callback_data="create_family")],
            ])
        )

async def show_main_menu(message: Message, user=None):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить задачу", callback_data="add_task")],
        [InlineKeyboardButton(text="📋 Все задачи семьи", callback_data="list_tasks")],
        [InlineKeyboardButton(text="👥 Участники", callback_data="members")],
        [InlineKeyboardButton(text="🔗 Пригласить в семью", callback_data="invite")],
    ])
    await message.answer("🏠 *Главное меню*", parse_mode="Markdown", reply_markup=keyboard)

@router.callback_query(F.data == "create_family")
async def cb_create_family(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Напиши название вашей семьи (например: *Ивановы*) 👨‍👩‍👧‍👦", parse_mode="Markdown")
    await state.set_state(FamilyStates.waiting_family_name)
    await callback.answer()

@router.message(FamilyStates.waiting_family_name)
async def process_family_name(message: Message, state: FSMContext):
    name = message.text.strip()
    code = "join_" + secrets.token_hex(4)
    family_id = await db.create_family(name, code)
    await db.set_user_family(message.from_user.id, family_id, is_admin=True)
    await state.clear()
    bot_info = await message.bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start={code}"
    await message.answer(
        f"✅ Семья *{name}* создана!\n\n🔗 Ссылка для приглашения:\n`{invite_link}`\n\nОтправь её родным — они сразу попадут в семью.",
        parse_mode="Markdown"
    )
    await show_main_menu(message)

@router.callback_query(F.data == "invite")
async def cb_invite(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user["family_id"]:
        await callback.answer("Сначала создай или вступи в семью!", show_alert=True)
        return
    family = await db.get_family(user["family_id"])
    bot_info = await callback.bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start={family['invite_code']}"
    await callback.message.answer(
        f"🔗 Ссылка для приглашения в семью *{family['name']}*:\n\n`{invite_link}`",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "add_task")
async def cb_add_task(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not user["family_id"]:
        await callback.answer("Сначала создай или вступи в семью!", show_alert=True)
        return
    await callback.message.answer(
        "📝 Напиши задачу в свободной форме, например:\n\n"
        "_«Напомни бабушке принять лекарство завтра в 9 утра»_\n"
        "_«Маше купить продукты сегодня в 18:00»_\n"
        "_«Мне позвонить врачу через 2 часа»_",
        parse_mode="Markdown"
    )
    await state.set_state(TaskStates.waiting_task_text)
    await callback.answer()

@router.message(TaskStates.waiting_task_text)
async def process_task_text(message: Message, state: FSMContext):
    await message.answer("🤖 Анализирую задачу...")
    parsed = await parse_task_with_ai(message.text)
    if not parsed:
        await message.answer(
            "❌ Не смог разобрать задачу. Попробуй написать чётче, например:\n"
            "_«Напомни маме позвонить врачу завтра в 10:00»_",
            parse_mode="Markdown"
        )
        await state.clear()
        return
    await state.update_data(parsed=parsed, original=message.text)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Верно", callback_data="confirm_task"),
            InlineKeyboardButton(text="✏️ Изменить", callback_data="retry_task")
        ]
    ])
    await message.answer(
        f"🤖 Вот что я понял:\n\n"
        f"👤 *Кому:* {parsed.get('who', '?')}\n"
        f"📌 *Задача:* {parsed.get('task', '?')}\n"
        f"⏰ *Когда:* {parsed.get('when', '?')}\n\n"
        "Всё верно?",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await state.set_state(TaskStates.confirm_ai_parse)

@router.callback_query(F.data == "retry_task")
async def cb_retry_task(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Попробуй написать задачу ещё раз, точнее указав кому, что и когда:")
    await state.set_state(TaskStates.waiting_task_text)
    await callback.answer()

@router.callback_query(F.data == "confirm_task", TaskStates.confirm_ai_parse)
async def cb_confirm_task(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    parsed = data["parsed"]
    user_db = await db.get_user(callback.from_user.id)
    family_id = user_db["family_id"]
    members = await db.get_family_members(family_id)
    who_name = parsed.get("who", "мне").lower()
    assigned_to = callback.from_user.id
    for m in members:
        if m["name"] and m["name"].lower() in who_name:
            assigned_to = m["id"]
            break
    try:
        remind_at = datetime.strptime(parsed["when"], "%Y-%m-%d %H:%M")
    except:
        remind_at = datetime.now()
    task_id = await db.create_task(
        family_id=family_id,
        assigned_to=assigned_to,
        created_by=callback.from_user.id,
        text=parsed["task"],
        remind_at=remind_at
    )
    if assigned_to != callback.from_user.id:
        try:
            await callback.bot.send_message(
                assigned_to,
                f"📬 Тебе назначена задача:\n\n*{parsed['task']}*\n\n⏰ Напомню: {remind_at.strftime('%d.%m в %H:%M')}",
                parse_mode="Markdown"
            )
        except:
            pass
    await callback.message.answer(
        f"✅ Задача создана!\n\n⏰ Напомню {remind_at.strftime('%d.%m в %H:%M')}",
        parse_mode="Markdown"
    )
    await state.clear()
    await show_main_menu(callback.message)
    await callback.answer()

@router.callback_query(F.data == "list_tasks")
async def cb_list_tasks(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user["family_id"]:
        await callback.answer("Сначала создай или вступи в семью!", show_alert=True)
        return
    tasks = await db.get_family_tasks(user["family_id"])
    members = await db.get_family_members(user["family_id"])
    member_map = {m["id"]: m["name"] for m in members}
    if not tasks:
        await callback.message.answer("📋 Задач пока нет. Добавь первую!")
        await callback.answer()
        return
    text = "📋 *Задачи семьи:*\n\n"
    for t in tasks:
        status = "✅" if t["done"] else "⏳"
        who = member_map.get(t["assigned_to"], "Неизвестно")
        when = t["remind_at"].strftime("%d.%m %H:%M") if t["remind_at"] else "—"
        text += f"{status} *{t['text']}*\n👤 {who} | ⏰ {when}\n\n"
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "members")
async def cb_members(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user["family_id"]:
        await callback.answer("Сначала создай или вступи в семью!", show_alert=True)
        return
    members = await db.get_family_members(user["family_id"])
    text = "👥 *Участники семьи:*\n\n"
    for m in members:
        role = "👑 Администратор" if m["is_admin"] else "👤 Участник"
        text += f"{role}: *{m['name']}*\n"
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("done_"))
async def cb_done(callback: CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    await db.mark_done(task_id)
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ *Выполнено!*",
        parse_mode="Markdown"
    )
    await callback.answer("Отлично! Задача выполнена 🎉")

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await show_main_menu(message)
