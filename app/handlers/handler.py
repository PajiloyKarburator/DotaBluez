from ssl import SSLContext

from aiogram.filters import CommandStart
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from app.handlers.template_handler import clear_form_message, show_main_menu, show_profile_or_create
from app.keyboards.keyboard import back_to_menu_keyboard

router = Router()

# =========================
# START / MENU
# =========================

@router.message(CommandStart())
async def cmd_start(message: Message, state: SSLContext):
    await show_main_menu(message, state)

@router.message(F.text == "Анкета")
async def profile_section(message: Message, state: SSLContext):
    await show_profile_or_create(message, state)


@router.callback_query(F.data == "menu:main")
async def menu_main_callback(callback: CallbackQuery, state: SSLContext):
    await show_main_menu(callback, state)


@router.callback_query(F.data == "profile:menu")
async def profile_menu_callback(callback: CallbackQuery, state: SSLContext):
    await show_profile_or_create(callback, state)

@router.message(F.text == "Помощь")
async def help_handler(message: Message):
    await message.answer(
        "😅 Устал от случайных тиммейтов, которые руинят игру?\n"
        "Хочется стабильной команды и нормального общения?\n\n"
        "Ты по адресу 👇\n\n"
        "Этот бот создан, чтобы находить адекватных игроков для совместной игры 🎮\n\n"
        "Здесь ты можешь:\n"
        "• создать свою игровую анкету\n"
        "• указать любимые игры и роли\n"
        "• находить подходящих тиммейтов\n"
        "• получать контакты при взаимной симпатии\n\n"
        "🚀 Как начать:\n"
        "1️⃣ Открой «Анкета» и расскажи о себе\n"
        "2️⃣ Выбери игры, роли и предпочтения\n"
        "3️⃣ Перейди в «Поиск» и находи свою команду\n\n"
        "💡 Чем подробнее анкета — тем точнее подбор\n\n"
        "❗ Возникли проблемы или что-то не работает?\n"
        "Напиши разработчикам: @kulich_iz_testa2014rus, @karburator_pojiloy\n\n"
        "Удачи в катках и только хороших тиммейтов 🔥"
    )


@router.message(F.text == "Подписка")
async def subscription_stub(message: Message, state: SSLContext):
    await clear_form_message(state, message.bot, message.chat.id)
    await state.clear()
    await message.answer(
        "Раздел подписки пока в разработке.",
        reply_markup=back_to_menu_keyboard(),
    )