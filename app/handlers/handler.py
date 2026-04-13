from aiogram.filters import CommandStart
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.db.models import User
from app.db.session import SessionLocal
from app.handlers.handler_search import search_service
from app.handlers.template_handler import clear_form_message, show_main_menu, show_profile_or_create
from app.keyboards.keyboard import main_menu_keyboard, teammates_carousel_keyboard
from app.repo.repository import UserRepo
from app.services.service_search import SearchService

router = Router()
user_repo = UserRepo()

# =========================
# START / MENU
# =========================


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await show_main_menu(message, state)


@router.message(F.text == "Анкета")
async def profile_section(message: Message, state: FSMContext):
    await show_profile_or_create(message, state)


@router.callback_query(F.data == "menu:main")
async def menu_main_callback(callback: CallbackQuery, state: FSMContext):
    await show_main_menu(callback, state)


@router.callback_query(F.data == "profile:menu")
async def profile_menu_callback(callback: CallbackQuery, state: FSMContext):
    await show_profile_or_create(callback, state)


def _empty_teammates_text() -> str:
    return (
        "<b>Мои тимейты</b>\n\n"
        "Здесь показываются только люди, с которыми у тебя был <b>взаимный лайк</b>.\n\n"
        "Пока таких нет — зайди в <b>«Поиск»</b>, листай анкеты и ставь ❤️. "
        "Когда симпатия окажется взаимной, контакт появится здесь."
    )


async def _teammate_card_html(teammate: User, viewer_id: int) -> str:
    tg_username = await search_service._get_tg_username(teammate.id)
    with SessionLocal() as db:
        badge = search_service.get_user_badge(db, teammate.id)
        show_rating = search_service._has_oracle(db, viewer_id)
    return SearchService._format_match_notification(
        teammate,
        tg_username,
        badge,
        show_rating=show_rating,
        show_match_header=False,
    )


async def _show_teammate_by_index(
    target: Message | CallbackQuery,
    *,
    user_id: int,
    index: int = 0,
    skip_callback_answer: bool = False,
) -> None:
    with SessionLocal() as db:
        teammates = user_repo.get_teammates(db, user_id)

    if not teammates:
        text = _empty_teammates_text()
        if isinstance(target, Message):
            await target.answer(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
        else:
            try:
                await target.message.edit_text(
                    text,
                    reply_markup=main_menu_keyboard(),
                    parse_mode="HTML",
                )
            except TelegramBadRequest as exc:
                if "message is not modified" not in str(exc).lower():
                    raise
            if not skip_callback_answer:
                await target.answer()
        return

    safe_index = max(0, min(index, len(teammates) - 1))
    teammate = teammates[safe_index]
    text = await _teammate_card_html(teammate, viewer_id=user_id)
    markup = teammates_carousel_keyboard(
        index=safe_index,
        total=len(teammates),
        teammate_id=teammate.id,
    )

    if isinstance(target, Message):
        await target.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        try:
            await target.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                raise
        if not skip_callback_answer:
            await target.answer()


@router.message(F.text == "Мои тимейты")
async def teammates_message(message: Message, state: FSMContext):
    await clear_form_message(state, message.bot, message.chat.id)
    await state.clear()
    await _show_teammate_by_index(message, user_id=message.from_user.id, index=0)


@router.callback_query(F.data.startswith("teammates:nav:"))
async def teammates_nav_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("Не удалось переключить карточку.", show_alert=True)
        return
    try:
        old_index = int(parts[2])
        new_index = int(parts[3])
    except ValueError:
        await callback.answer("Не удалось переключить карточку.", show_alert=True)
        return

    with SessionLocal() as db:
        teammates = user_repo.get_teammates(db, callback.from_user.id)
    total = len(teammates)
    if total == 0:
        await callback.answer("Список тиммейтов пуст.", show_alert=True)
        return
    if new_index < 0 or new_index >= total:
        await callback.answer("Такой карточки нет.", show_alert=True)
        return

    if new_index == total - 1 and new_index > old_index:
        await callback.answer(
            "Конец списка — это последний тиммейт.",
            show_alert=True,
        )
    elif new_index == 0 and new_index < old_index:
        await callback.answer(
            "Начало списка — это первый тиммейт.",
            show_alert=True,
        )
    else:
        await callback.answer()

    await _show_teammate_by_index(
        callback,
        user_id=callback.from_user.id,
        index=new_index,
        skip_callback_answer=True,
    )


@router.callback_query(F.data.startswith("teammates:remove:"))
async def teammates_remove_callback(callback: CallbackQuery):
    try:
        teammate_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("Некорректный ID", show_alert=True)
        return

    with SessionLocal() as db:
        user_repo.remove_teammate(db, callback.from_user.id, teammate_id)
        remaining = user_repo.get_teammates(db, callback.from_user.id)

    if not remaining:
        await callback.answer(
            "Это был последний в списке. Новые тиммейты появятся после следующего мэтча.",
            show_alert=True,
        )
    else:
        await callback.answer("Удалён из списка")

    await _show_teammate_by_index(
        callback,
        user_id=callback.from_user.id,
        index=0,
        skip_callback_answer=True,
    )


@router.callback_query(F.data == "teammates:noop")
async def teammates_noop(callback: CallbackQuery):
    await callback.answer()


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
