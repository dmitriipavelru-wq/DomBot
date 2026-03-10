from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import database as db

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

def start_scheduler(bot: Bot):
    scheduler.add_job(send_reminders, "interval", minutes=1, args=[bot])
    scheduler.start()

async def send_reminders(bot: Bot):
    tasks = await db.get_pending_reminders()
    for task in tasks:
        try:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Сделано", callback_data=f"done_{task['id']}")
            ]])
            await bot.send_message(
                chat_id=task["assigned_to"],
                text=f"⏰ *Напоминание!*\n\n{task['text']}",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            await db.mark_reminded(task["id"])
        except Exception as e:
            print(f"Не удалось отправить напоминание: {e}")
