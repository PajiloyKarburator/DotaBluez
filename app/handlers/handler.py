from aiogram.filters import CommandStart
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.db.session import SessionLocal
from app.handlers.template_handler import clear_form_message, show_main_menu, show_profile_or_create
from app.keyboards.keyboard import (
    GAMES,
    GAME_TAGS,
    main_menu_keyboard,
    teammates_carousel_keyboard,
)
from app.repo.repository import UserRepo

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


def _teammate_card_text(teammate) -> str:
    games = (
        ", ".join(GAMES.get(game_key, game_key) for game_key in (teammate.games or []))
        if teammate.games
        else "не указаны"
    )

    tag_titles: list[str] = []
    for tag_key in (teammate.tags or []):
        tag_title = tag_key
        for tags_map in GAME_TAGS.values():
            if tag_key in tags_map:
                tag_title = tags_map[tag_key]
                break
        tag_titles.append(tag_title)
    tags = ", ".join(tag_titles) if tag_titles else "не указаны"
    description = teammate.description or "Описание не указано"
    return (
        f"🤝 <b>{teammate.username or 'Игрок'}, {teammate.age} лет</b>\n\n"
        f"🎮 Игры: {games}\n"
        f"🏷 Роли: {tags}\n"
        f"📝 {description}"
    )


async def _show_teammate_by_index(
    target: Message | CallbackQuery,
    *,
    user_id: int,
    index: int = 0,
) -> None:
    with SessionLocal() as db:
        teammates = user_repo.get_teammates(db, user_id)

    if not teammates:
        text = "Пока нет взаимных лайков. Как только будет мэтч, игрок появится здесь."
        if isinstance(target, Message):
            await target.answer(text, reply_markup=main_menu_keyboard())
        else:
            await target.message.edit_text(text, reply_markup=None)
            await target.answer()
        return

    safe_index = index % len(teammates)
    teammate = teammates[safe_index]
    text = _teammate_card_text(teammate)
    markup = teammates_carousel_keyboard(
        index=safe_index,
        total=len(teammates),
        teammate_id=teammate.id,
    )

    if isinstance(target, Message):
        await target.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await target.answer()


@router.message(F.text == "Мои тимейты")
async def teammates_message(message: Message, state: FSMContext):
    await clear_form_message(state, message.bot, message.chat.id)
    await state.clear()
    await _show_teammate_by_index(message, user_id=message.from_user.id, index=0)


@router.callback_query(F.data.startswith("teammates:show:"))
async def teammates_show_callback(callback: CallbackQuery):
    try:
        index = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("Некорректный индекс", show_alert=True)
        return
    await _show_teammate_by_index(
        callback,
        user_id=callback.from_user.id,
        index=index,
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
    await callback.answer("Тиммейт удалён из списка")
    await _show_teammate_by_index(callback, user_id=callback.from_user.id, index=0)


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
