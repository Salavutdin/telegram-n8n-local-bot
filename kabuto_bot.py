import os
import asyncio
import logging
from threading import Thread
from flask import Flask, request
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

# Читаем токен бота из .env
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не найден TELEGRAM_BOT_TOKEN в .env")

# Указываем URL вебхука n8n (замени на свой!)
# для тестирования N8N_WEBHOOK_URL = "http://localhost:5678/webhook-test/23467e56-1e59-4b55-a7d0-2ce125cc26ac"
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/23467e56-1e59-4b55-a7d0-2ce125cc26ac"
FLASK_PORT = 8000  # Порт, на котором будет работать Flask

# Создаем экземпляры бота и диспетчера aiogram
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Создаем Flask-приложение
app = Flask(__name__)

# Создаем новый event loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Обработчик входящих сообщений в Telegram
@dp.message(F.text)
async def handle_message(message: Message):
    """
    Когда пользователь отправляет сообщение боту, 
    оно пересылается в n8n через вебхук.
    """
    params = {
        "chat_id": message.chat.id,
        "text": message.text,
    }
    try:
        response = requests.get(N8N_WEBHOOK_URL, params=params)
        await message.answer(f"Отправлено в n8n. Ответ: {response.text}")
    except Exception as e:
        await message.answer(f"Ошибка при отправке в n8n: {e}")

# Обработчик запросов из n8n (принимаем данные от n8n)
@app.route("/from-n8n", methods=["POST"])
def from_n8n():
    """
    n8n отправляет POST-запрос с chat_id и reply.
    Бот получает эти данные и отправляет сообщение в Телеграм.
    """
    data = request.get_json()
    chat_id = data.get("chat_id")
    reply = data.get("reply")
    
    if not chat_id or not reply:
        return {"error": "chat_id и reply обязательны"}, 400
    
    # Отправляем сообщение в Телеграм в основном event loop
    loop.call_soon_threadsafe(
        asyncio.create_task,
        bot.send_message(chat_id=chat_id, text=reply)
    )
    return {"status": "ok"}

# Запуск Flask в отдельном потоке
def run_flask():
    """
    Запускаем Flask-сервер, чтобы принимать данные от n8n.
    """
    app.run(host="0.0.0.0", port=FLASK_PORT)

# Запуск бота aiogram
async def run_bot():
    """
    Запускаем aiogram-бота в режиме поллинга.
    """
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

# Основной запуск
if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()  # Запускаем Flask в фоне
    loop.run_until_complete(run_bot())  # Запускаем aiogram-бота
