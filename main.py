import os
import asyncio
import logging
import aiohttp
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- ИМПОРТЫ ДЛЯ ОБХОДА БЛОКИРОВКИ ---
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.client.default import DefaultBotProperties
# ------------------------------------------

# Локальные модули
import parser_logic
import schedule_logic
import keyboards
import database

# Загружаем настройки из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# Объявляем бота глобально, чтобы хендлеры и функции могли к нему обращаться
bot: Bot = None
dp = Dispatcher()

database.init_db()

# --- МИДДЛВАР ДЛЯ СТАТИСТИКИ ---

@dp.message.outer_middleware()
async def user_logging_middleware(handler, event, data):
    if isinstance(event, types.Message):
        user = event.from_user
        database.log_user(user.id, user.username, user.first_name, user.last_name)
    return await handler(event, data)

# Пути к файлам
DATA_DIR = "data"

# Состояния для админа
class AdminStates(StatesGroup):
    waiting_for_file = State()

# Состояния для обратной связи
class FeedbackStates(StatesGroup):
    waiting_for_feedback = State()

# Функция для безопасного удаления сообщения
async def delete_prev_msg(state: FSMContext):
    data = await state.get_data()
    prev_msg_id = data.get("last_msg_id")
    chat_id = data.get("chat_id")
    if prev_msg_id and chat_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=prev_msg_id)
        except Exception:
            pass

# --- КОМАНДА /START ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.set_state(None)
    database.log_user(
        message.from_user.id, 
        message.from_user.username, 
        message.from_user.first_name, 
        message.from_user.last_name
    )
    await message.answer(
        f"👋 *Добро пожаловать, {message.from_user.first_name}!*\n\n"
        "Я — школьный помощник. Здесь вы найдете меню столовой и актуальное расписание уроков.\n\n"
        "✨ *Выберите интересующий вас раздел:*",
        reply_markup=keyboards.main_menu(),
        parse_mode="Markdown"
    )

# --- АДМИН-ФУНКЦИИ ---

@dp.message(Command("stats"))
async def show_stats(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("🚫 У вас нет прав администратора.")
        return

    stats = database.get_stats()
    await message.answer(
        "📊 *СТАТИСТИКА БОТА*\n\n"
        f"👥 Всего пользователей: *{stats['total']}*\n"
        f"🆕 Новых сегодня: *{stats['new_today']}*\n"
        f"👥 Активно сегодня: *{stats['active_today']}*",
        parse_mode="Markdown"
    )

@dp.message(Command("update_menu"))
async def admin_update_menu(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("🚫 У вас нет прав администратора.")
        return
    
    users = database.get_all_users()
    count = 0
    await message.answer(f"⏳ Начинаю рассылку обновления меню для {len(users)} пользователей...")
    
    for user_id in users:
        try:
            await bot.send_message(
                user_id,
                "🔄 *Меню бота обновлено!*\n\nМы добавили новую кнопку: *💡 Предложить идею / Сообщить о баге*.\nТеперь вы можете легко связаться с администратором прямо из главного меню!",
                reply_markup=keyboards.main_menu(),
                parse_mode="Markdown"
            )
            count += 1
            await asyncio.sleep(0.05)  # Небольшая пауза, чтобы не превысить лимиты Telegram
        except Exception as e:
            logging.error(f"Не удалось отправить обновленное меню пользователю {user_id}: {e}")
            
    await message.answer(f"✅ Обновленное меню успешно отправлено {count} пользователям из {len(users)}.")

# --- МЕНЮ ПИТАНИЯ ---

@dp.message(F.text == "😋 Посмотреть меню")
async def show_dates(message: types.Message, state: FSMContext):
    await delete_prev_msg(state)
    dates = parser_logic.get_available_dates()
    if not dates:
        await message.answer("😔 *Извините, меню столовой пока не загружено.*", parse_mode="Markdown")
        return
    
    sent_msg = await message.answer(
        "🍽 *МЕНЮ СТОЛОВОЙ*\n🗓 Выберите дату:",
        reply_markup=keyboards.dates_keyboard(dates),
        parse_mode="Markdown"
    )
    await state.update_data(last_msg_id=sent_msg.message_id, chat_id=message.chat.id)
    try: await message.delete()
    except: pass

@dp.callback_query(F.data == "back_to_dates")
async def back_to_dates(callback: types.CallbackQuery):
    dates = parser_logic.get_available_dates()
    await callback.message.edit_text(
        "🍽 *МЕНЮ СТОЛОВОЙ*\n🗓 Выберите дату:",
        reply_markup=keyboards.dates_keyboard(dates),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("date_"))
async def show_menu(callback: types.CallbackQuery):
    target_date = callback.data.split("date_")[1]
    menu_text = parser_logic.get_menu_by_date(target_date)
    await callback.message.edit_text(
        menu_text,
        reply_markup=keyboards.back_menu_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

# --- РАСПИСАНИЕ УРОКОВ ---

@dp.message(F.text == "📚 Расписание уроков")
async def show_classes(message: types.Message, state: FSMContext):
    await delete_prev_msg(state)
    classes = schedule_logic.get_classes()
    if not classes:
        await message.answer("😔 *Извините, расписание уроков пока недоступно.*", parse_mode="Markdown")
        return
    
    sent_msg = await message.answer(
        "🎓 *РАСПИСАНИЕ УРОКОВ*\n👥 Выберите ваш класс:",
        reply_markup=keyboards.classes_keyboard(classes),
        parse_mode="Markdown"
    )
    await state.update_data(last_msg_id=sent_msg.message_id, chat_id=message.chat.id)
    try: await message.delete()
    except: pass

@dp.callback_query(F.data == "back_to_classes")
async def back_to_classes(callback: types.CallbackQuery):
    classes = schedule_logic.get_classes()
    await callback.message.edit_text(
        "🎓 *РАСПИСАНИЕ УРОКОВ*\n👥 Выберите ваш класс:",
        reply_markup=keyboards.classes_keyboard(classes),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("class_"))
async def show_days(callback: types.CallbackQuery):
    class_name = callback.data.split("_")[1]
    await callback.message.edit_text(
        f"📅 *КЛАСС: {class_name}*\nВыберите день недели:",
        reply_markup=keyboards.days_keyboard(class_name),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("sched_"))
async def show_class_schedule(callback: types.CallbackQuery):
    data = callback.data.split("_")
    class_name, day = data[1], data[2]
    schedule_text = schedule_logic.get_schedule(class_name, day)
    await callback.message.edit_text(
        schedule_text,
        reply_markup=keyboards.back_to_days_keyboard(class_name),
        parse_mode="Markdown"
    )
    await callback.answer()

# --- ОБРАТНАЯ СВЯЗЬ ---

@dp.message(F.text == "💡 Предложить идею / Сообщить о баге")
async def start_feedback(message: types.Message, state: FSMContext):
    await delete_prev_msg(state)
    sent_msg = await message.answer(
        "✍️ *Пожалуйста, опишите вашу идею или найденный баг.*\n\n"
        "Ваше сообщение будет отправлено администратору бота.\n"
        "Если хотите отменить, нажмите /start или выберите другой пункт меню.",
        parse_mode="Markdown"
    )
    await state.set_state(FeedbackStates.waiting_for_feedback)
    await state.update_data(last_msg_id=sent_msg.message_id, chat_id=message.chat.id)
    try: await message.delete()
    except: pass

@dp.message(FeedbackStates.waiting_for_feedback)
async def process_feedback(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return
        
    user_info = f"От пользователя: @{message.from_user.username} (ID: {message.from_user.id})" if message.from_user.username else f"От пользователя: {message.from_user.first_name} (ID: {message.from_user.id})"
    
    admin_message = f"💡 *Новое сообщение (Идея/Баг)*\n\n{user_info}\n\n📝 *Текст:*\n{message.text}"
    
    try:
        await bot.send_message(ADMIN_ID, admin_message, parse_mode="Markdown")
        await message.answer("✅ *Ваше сообщение успешно отправлено администратору!* Спасибо за обратную связь.", parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Failed to send feedback to admin: {e}")
        await message.answer("❌ Произошла ошибка при отправке сообщения. Попробуйте позже.")
        
    await state.clear()

# --- ЗАГРУЗКА ФАЙЛОВ (АДМИН) ---

@dp.message(Command("upload"))
async def admin_upload(message: types.Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("🚫 У вас нет прав администратора.")
        return
    
    await message.answer(
        "📤 *РЕЖИМ ЗАГРУЗКИ МЕНЮ*\n\n"
        "Отправьте один или несколько Excel файлов (.xlsx).\n"
        "Когда закончите, отправьте любое текстовое сообщение.",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_file)

@dp.message(AdminStates.waiting_for_file, F.document)
async def process_file(message: types.Message):
    if not message.document.file_name.endswith(".xlsx"):
        await message.answer(f"❌ Файл {message.document.file_name} пропущен (нужен .xlsx)")
        return

    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    file_path = os.path.join(DATA_DIR, message.document.file_name)
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, file_path)
    parser_logic.fix_excel_format(file_path)
    await message.answer(f"✅ Файл {message.document.file_name} успешно загружен!")

@dp.message(AdminStates.waiting_for_file)
async def finish_upload(message: types.Message, state: FSMContext):
    await message.answer("🆗 Режим загрузки завершен. Меню обновлено!", reply_markup=keyboards.main_menu())
    await state.clear()

    	# --- УДАЛЕНИЕ МЕНЮ (АДМИН) ---

@dp.message(Command("delete"))
async def admin_delete_start(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("🚫 У вас нет прав администратора.")
        return
    
    dates = parser_logic.get_available_dates()
    if not dates:
        await message.answer("🤷 Нет доступных дат для удаления.")
        return
    
    await message.answer(
        "🗑 *РЕЖИМ УДАЛЕНИЯ МЕНЮ*\nВыберите дату, которую хотите удалить:",
        reply_markup=keyboards.admin_delete_dates_keyboard(dates),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("admin_del_"))
async def process_admin_delete(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("🚫 Доступ запрещен.", show_alert=True)
        return
    
    target_date = callback.data.split("admin_del_")[1]
    success = parser_logic.delete_menu_by_date(target_date)
    
    if success:
        await callback.answer(f"✅ Меню на {target_date} удалено!", show_alert=True)
    else:
        await callback.answer(f"❌ Не удалось удалить меню на {target_date}.", show_alert=True)
    
    # Обновляем список или удаляем сообщение
    dates = parser_logic.get_available_dates()
    if dates:
        await callback.message.edit_text(
            "🗑 *РЕЖИМ УДАЛЕНИЯ МЕНЮ*\nВыберите следующую дату или нажмите Отмена:",
            reply_markup=keyboards.admin_delete_dates_keyboard(dates),
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text("✅ Все меню удалены.")

@dp.callback_query(F.data == "admin_cancel_delete")
async def cancel_admin_delete(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer("Отмена удаления")

    
# --- ЗАПУСК БОТА ---

async def main():
    global bot
    
    CUSTOM_API_URL = "https://tg-proxy-bot.ahunovniaz04.workers.dev"
    custom_server = TelegramAPIServer.from_base(CUSTOM_API_URL)
    
    # ВАЖНО: Добавляем timeout=15.0 (просто числом!)
    # Теперь общее время ожидания будет: 15 (сессия) + 10 (polling) = 25 секунд.
    # Это МЕНЬШЕ лимита Cloudflare (30 сек), поэтому бот перестанет "зависать" в пустоте.
    async with AiohttpSession(api=custom_server, timeout=15.0) as session:
        bot = Bot(
            token=BOT_TOKEN, 
            session=session,
            default=DefaultBotProperties(parse_mode="Markdown")
        )
        
        print("Бот запущен и проверяет сообщения!")
        try:
            # Опрос каждые 10 секунд
            await dp.start_polling(bot, polling_timeout=1)
        finally:
            pass 

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")