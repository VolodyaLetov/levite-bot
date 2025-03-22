import asyncio
import sqlite3
import json
import pandas as pd
from telebot.async_telebot import AsyncTeleBot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# === Настройки бота === #
TOKEN = "7382794283:AAFgyE1omxNsALuiSzH9UZXgk2y54OdkxHc"
CHANNEL_USERNAME = "@levite_test"
bot = AsyncTeleBot(TOKEN)

# === Хранилище пользователей (JSON) === #
USER_DATA_FILE = "user_data.json"

try:
    with open(USER_DATA_FILE, "r", encoding="utf-8") as file:
        user_data = json.load(file)
except FileNotFoundError:
    user_data = {}

def save_user_data():
    """Сохранение данных пользователей"""
    with open(USER_DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(user_data, file, ensure_ascii=False, indent=4)

# === Инициализация базы данных === #
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        name TEXT,
        username TEXT,
        is_admin INTEGER DEFAULT 0
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        start_time TEXT,
        end_time TEXT,
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    )
    ''')

    conn.commit()
    conn.close()

# === Функции работы со сменами === #
def start_shift(telegram_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM employees WHERE telegram_id=?", (telegram_id,))
    employee = cursor.fetchone()

    if employee:
        cursor.execute("INSERT INTO shifts (employee_id, start_time) VALUES (?, datetime('now'))", (employee[0],))
        conn.commit()
        return "✅ Начало смены зафиксировано!"
    return "❌ Вы не зарегистрированы."

def end_shift(telegram_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM employees WHERE telegram_id=?", (telegram_id,))
    employee = cursor.fetchone()

    if employee:
        cursor.execute("UPDATE shifts SET end_time = datetime('now') WHERE employee_id = ? AND end_time IS NULL", (employee[0],))
        conn.commit()
        return "✅ Конец смены зафиксирован!"
    return "❌ Вы не зарегистрированы."

# === Команды бота === #
@bot.message_handler(commands=['start'])
async def send_welcome(message):
    """Приветствие с проверкой регистрации"""
    chat_id = str(message.chat.id)
    user = user_data.get(chat_id)

    if user:
        if user.get("state") == "logged_in":
            await bot.send_message(chat_id, f"✅ Вы уже вошли, {user['name']}!")
            await show_main_menu(chat_id, user.get("is_admin", False))
        elif user.get("state") == "registered":
            user["state"] = "awaiting_login_password"
            save_user_data()
            await bot.send_message(chat_id, f"Привет, {user['name']}! Введите ваш пароль для входа:")
        else:
            await bot.send_message(chat_id, "Привет! Введите /register для регистрации.")
    else:
        await bot.send_message(chat_id, "Привет! Введите /register для регистрации.")

@bot.message_handler(func=lambda message: user_data.get(str(message.chat.id), {}).get("state") == "awaiting_login_password")
async def login_password_check(message):
    """Проверка пароля и запуск меню"""
    chat_id = str(message.chat.id)
    user = user_data.get(chat_id)

    if message.text.strip() == user.get("password"):
        user["state"] = "logged_in"
        user["is_admin"] = False  

        try:
            member = await bot.get_chat_member(CHANNEL_USERNAME, int(chat_id))
            if member.status in ['administrator', 'creator']:
                user["is_admin"] = True
        except Exception as e:
            print(f"Ошибка при проверке админа: {e}")

        save_user_data()
        await bot.send_message(chat_id, f"✅ Вход выполнен! Добро пожаловать, {user['name']}!")
        await show_main_menu(chat_id, user["is_admin"])
    else:
        await bot.send_message(chat_id, "❌ Неверный пароль. Попробуйте снова.")

# === Меню с кнопками === #
async def show_main_menu(chat_id, is_admin=False):
    """Главное меню"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        KeyboardButton("📅 Мои смены"),
        KeyboardButton("📍 Отметиться"),
        KeyboardButton("👤 Личная информация")
    )

    if is_admin:
        keyboard.add(KeyboardButton("👥 Список работников"))

    await bot.send_message(chat_id, "📋 Главное меню:", reply_markup=keyboard)

# === Обработчик кнопок === #
@bot.message_handler(func=lambda message: message.text in ["📅 Мои смены", "📍 Отметиться", "👤 Личная информация", "👥 Список работников"])
async def menu_handler(message):
    """Обработка кнопок"""
    chat_id = str(message.chat.id)
    user = user_data.get(chat_id)

    if message.text == "📅 Мои смены":
        await bot.send_message(chat_id, "📆 У вас пока нет запланированных смен.")
    
    elif message.text == "📍 Отметиться":
        response = start_shift(chat_id) if not check_active_shift(chat_id) else end_shift(chat_id)
        await bot.send_message(chat_id, response)

    elif message.text == "👤 Личная информация":
        user_info = (
            f"👤 Имя: {user.get('name', 'Неизвестно')}\n"
            f"🔑 Логин: {user.get('username', 'Неизвестно')}\n"
            f"🛠 Роль: {'Администратор' if user.get('is_admin') else 'Официант'}"
        )
        await bot.send_message(chat_id, user_info)

    elif message.text == "👥 Список работников" and user.get("is_admin"):
        await bot.send_message(chat_id, "📋 Список работников пока пуст.")

# === Основной цикл === #
async def main():
    print("Бот запущен...")
    init_db()
    await bot.polling()

if __name__ == "__main__":
    asyncio.run(main())
