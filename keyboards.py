from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Главное меню (Reply)
def main_menu():
    kb = [
        [KeyboardButton(text="😋 Посмотреть меню"), KeyboardButton(text="📚 Расписание уроков")],
        [KeyboardButton(text="💡 Предложить идею / Сообщить о баге")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, input_field_placeholder="Выберите раздел...")

# --- КЛАВИАТУРЫ МЕНЮ ПИТАНИЯ ---

def dates_keyboard(dates: list):
    builder = InlineKeyboardBuilder()
    for date in dates:
        builder.row(InlineKeyboardButton(text=f"📅 {date}", callback_data=f"date_{date}"))
    return builder.as_markup()

def admin_delete_dates_keyboard(dates: list):
    builder = InlineKeyboardBuilder()
    for date in dates:
        builder.row(InlineKeyboardButton(text=f"🗑 Удалить {date}", callback_data=f"admin_del_{date}"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel_delete"))
    return builder.as_markup()


def back_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к датам", callback_data="back_to_dates")]
    ])

# --- КЛАВИАТУРЫ РАСПИСАНИЯ ---

def classes_keyboard(classes: list):
    builder = InlineKeyboardBuilder()
    for cls in classes:
        builder.add(InlineKeyboardButton(text=f"👥 {cls}", callback_data=f"class_{cls}"))
    builder.adjust(3) 
    return builder.as_markup()

def days_keyboard(class_name: str):
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]
    builder = InlineKeyboardBuilder()
    # Группируем по 2 дня в ряд
    for i in range(0, len(days), 2):
        builder.row(
            InlineKeyboardButton(text=f"🔹 {days[i]}", callback_data=f"sched_{class_name}_{days[i]}"),
            InlineKeyboardButton(text=f"🔹 {days[i+1]}", callback_data=f"sched_{class_name}_{days[i+1]}")
        )
    builder.row(InlineKeyboardButton(text="⬅️ К выбору класса", callback_data="back_to_classes"))
    return builder.as_markup()

def back_to_days_keyboard(class_name: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к дням", callback_data=f"class_{class_name}")]
    ])
