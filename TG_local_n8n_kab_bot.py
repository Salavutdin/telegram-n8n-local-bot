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

# Читаем токен бота
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не найден TELEGRAM_BOT_TOKEN в .env")

# Читаем параметры n8n из .env
N8N_PATH = os.getenv("N8N_WEBHOOK_PATH", "23467e56-1e59-4b55-a7d0-2ce125cc26ac")  # Можно менять по желанию
N8N_MODE = os.getenv("N8N_MODE", "prod")  # "test" или "prod"
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678")

# Автоматически выбираем URL вебхука в зависимости от режима
if N8N_MODE == "test":
    N8N_WEBHOOK_URL = f"{N8N_BASE_URL}/webhook-test/{N8N_PATH}"
else:
    N8N_WEBHOOK_URL = f"{N8N_BASE_URL}/webhook/{N8N_PATH}"

# Порт, на котором работает Flask-сервер (используется n8n для ответа)
FLASK_PORT = 8000

# Создаем экземпляры aiogram-бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Flask-приложение для получения сообщений от n8n
app = Flask(__name__)

# Новый event loop для асинхронных задач
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# 📥 Приём сообщений от Telegram и отправка в n8n
@dp.message(F.text)
async def handle_message(message: Message):
    """
    Обрабатывает входящее сообщение от пользователя и пересылает его в n8n.
    """
    params = {
        "chat_id": message.chat.id,
        "text": message.text,
    }
    try:
        response = requests.get(N8N_WEBHOOK_URL, params=params)
        # await message.answer(f"Отправлено в n8n. Ответ: {response.text}")
        await message.answer(f"Секунду, печатаю...")
    except Exception as e:
        await message.answer(f"Ошибка при отправке в n8n: {e}")

# 📤 Приём ответа от n8n (из ноды HTTP Request)
@app.route("/from-n8n", methods=["POST"])
def from_n8n():
    """
    Получает POST-запрос от n8n и отправляет ответ пользователю в Telegram.
    """
    data = request.get_json()
    chat_id = data.get("chat_id")
    reply = data.get("reply")

    if not chat_id or not reply:
        return {"error": "chat_id и reply обязательны"}, 400

    # Асинхронная отправка сообщения
    loop.call_soon_threadsafe(
        asyncio.create_task,
        bot.send_message(chat_id=chat_id, text=reply)
    )
    return {"status": "ok"}

# Запуск Flask-сервера в фоновом потоке
def run_flask():
    app.run(host="0.0.0.0", port=FLASK_PORT)

# Запуск aiogram-бота
async def run_bot():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

# 🚀 Точка входа
if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    loop.run_until_complete(run_bot())
