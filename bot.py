from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import asyncio

from app.handlers.template_handler import router as template_handler
from app.handlers.handler_search import router as search_router
from app.handlers.handler_search import search_service
from app.handlers.handler_content import router as content_router
from app.handlers.handler import router as main_router

from app.config.cfg import BOT_TOKEN


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Передаём бота в сервис поиска для отправки уведомлений
    search_service.set_bot(bot)

    dp = Dispatcher()
    dp.include_router(template_handler)
    dp.include_router(search_router)
    dp.include_router(content_router)
    dp.include_router(main_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())