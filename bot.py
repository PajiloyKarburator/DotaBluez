from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import asyncio

from app.config.cfg import BOT_TOKEN

from app.handlers import template_handler, handler, handler_content
from app.handlers.handler_search import router as search_router



async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(template_handler.router)
    dp.include_router(handler.router)
    dp.include_router(search_router)
    dp.include_router(handler_content.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())