import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from app.repo.repository import Database, ProfileRepository
from app.services.service_search import SearchService
from app.handlers import handler_search


async def main():
    bot_token = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
    db_dsn = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/dotabluez",
    )

    # 1. Подключаем БД
    db = Database(dsn=db_dsn)
    await db.connect()

    # 2. Создаём репозиторий
    repo = ProfileRepository(db=db)

    # 3. Создаём сервис поиска и передаём в хэндлер
    search_service = SearchService(repo=repo)
    handler_search.search_service = search_service

    # 4. Настраиваем бота
    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # 5. Подключаем роутер
    dp.include_router(handler_search.router)

    try:
        print("Бот запущен!")
        await dp.start_polling(bot)
    finally:
        await db.disconnect()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())