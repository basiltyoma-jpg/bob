import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Создание бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Обработчик команды /start
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Я простой бот на Aiogram.\n"
        "Напиши мне что-нибудь, и я повторю это."
    )

# Обработчик команды /help
@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "Доступные команды:\n"
        "/start - начать работу\n"
        "/help - помощь"
    )

# Эхо-обработчик (повторяет сообщения пользователя)
@dp.message()
async def echo_handler(message: Message):
    await message.answer(f"Вы написали: {message.text}")

# Точка входа
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())