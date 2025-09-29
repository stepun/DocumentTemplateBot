import asyncio
import logging
import os
from dotenv import load_dotenv

from bot import DocumentBot

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

# Настройка отдельного логгера для пользователей
user_logger = logging.getLogger('user_activity')
user_handler = logging.FileHandler('user_activity.log')
user_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
user_logger.addHandler(user_handler)
user_logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)

async def main():
    """Основная функция запуска бота"""
    bot_token = os.getenv("BOT_TOKEN")

    if not bot_token:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        return

    # Создаем необходимые директории
    os.makedirs("templates", exist_ok=True)
    os.makedirs("filled_documents", exist_ok=True)
    os.makedirs("config", exist_ok=True)

    logger.info("Создание экземпляра бота...")
    bot = DocumentBot(bot_token)

    try:
        logger.info("Запуск бота...")
        await bot.start_polling()
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Ошибка при работе бота: {e}")
    finally:
        logger.info("Остановка бота...")

if __name__ == "__main__":
    asyncio.run(main())