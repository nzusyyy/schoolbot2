import json
import os
import re

SCHEDULE_FILE = "raspisanie.json"

def get_classes():
    if not os.path.exists(SCHEDULE_FILE): return []
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    classes = sorted(list(set(item["class"] for item in data)), key=lambda x: (int(re.sub(r'\D', '', x)), x))
    return classes

def format_lesson(lesson: str):
    """Красиво выделяет кабинет из названия урока, учитывая пометки типа (К)"""
    # Ищем последние скобки в строке, где обычно указан кабинет
    # Регулярное выражение ищет (текст) в самом конце строки
    match = re.search(r'\(([^()]+)\)$', lesson.strip())
    
    if match:
        room = match.group(1) # Содержимое последних скобок (кабинет)
        # Название предмета - это всё, что ДО этих скобок
        subject = lesson[:match.start()].strip()
        return f"  ▫️ {subject} — *[{room}]*"
    
    return f"  ▫️ {lesson}"

def get_schedule(class_name: str, day: str):
    if not os.path.exists(SCHEDULE_FILE): return "❌ Файл расписания не найден."
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    schedule = next((item for item in data if item["class"] == class_name and item["day"] == day), None)
    if not schedule: return f"🤷 Расписание для {class_name} на {day} не найдено."
    
    msg = f"📚 *УРОКИ: {class_name.upper()}*\n"
    msg += f"🗓 `{day}`\n"
    msg += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    count = 0
    for i, lesson in enumerate(schedule["lessons"], 1):
        clean_lesson = str(lesson).strip()
        if clean_lesson and clean_lesson != "-" and clean_lesson != "nan":
            msg += f"`{i}.` {format_lesson(clean_lesson)}\n"
            count += 1
    
    if count == 0:
        msg += "🌴 *Занятий нет!*\n"
        
    msg += "\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    msg += "✍️ _Удачного дня и хороших оценок!_"
    return msg
