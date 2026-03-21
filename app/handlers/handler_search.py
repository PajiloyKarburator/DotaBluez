from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from app.db.session import SessionLocal
from app.keyboards.keyboard import GAMES, GAME_TAGS, main_menu_keyboard
from app.services.service_search import SearchService

router = Router()

# Единственный экземпляр сервиса — хранит квоты и просмотренные анкеты
search_service = SearchService()


class SearchStates(StatesGroup):
    browsing = State()


# ──────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────

def _format_card(card) -> str:
    """Форматирует текст карточки анкеты."""

    # Переводим машинные ключи игр в читаемые названия
    games_display = []
    for g in (card.games or []):
        games_display.append(GAMES.get(g, g))
    games_str = ", ".join(games_display) if games_display else "не указаны"

    # Переводим машинные ключи тегов в читаемые названия
    tags_display = []
    for tag_key in (card.tags or []):
        tag_name = tag_key  # fallback — сам ключ
        for game_tags in GAME_TAGS.values():
            if tag_key in game_tags:
                tag_name = game_tags[tag_key]
                break
        tags_display.append(tag_name)
    tags_str = ", ".join(tags_display) if tags_display else "не указаны"

    return (
        f"<b>👤 {card.username or 'Игрок'}, {card.age} лет</b>\n\n"
        f"🎮 <b>Игры:</b> {games_str}\n"
        f"🏷 <b>Роли:</b> {tags_str}\n\n"
        f"📝 {card.description or 'Описание не указано'}\n\n"
        f"⭐ Рейтинг: {card.rating if card.rating is not None else '—'}"
    )


def _card_keyboard() -> InlineKeyboardMarkup:
    """3 кнопки: лайк, дизлайк, вернуться к профилю."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👎", callback_data="search:dislike"),
                InlineKeyboardButton(text="❤️", callback_data="search:like"),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Вернуться к профилю",
                    callback_data="search:back_to_profile",
                ),
            ],
        ]
    )


def _no_views_text(seconds_left: int) -> str:
    """Текст когда просмотры закончились."""
    if seconds_left <= 0:
        return "📭 Просмотры закончились. Попробуй ещё раз!"

    minutes = seconds_left // 60
    seconds = seconds_left % 60

    return (
        "⏳ <b>Просмотры закончились!</b>\n\n"
        f"Следующая анкета будет доступна через "
        f"<b>{minutes} мин {seconds} сек</b>."
    )


async def _send_card(target: Message | CallbackQuery, card, *, edit: bool = False) -> None:
    """Отправить или отредактировать карточку."""
    text = _format_card(card)
    keyboard = _card_keyboard()

    if edit and isinstance(target, CallbackQuery):
        # Пробуем отредактировать текущее сообщение
        try:
            if card.img:
                await target.message.edit_media(
                    media=InputMediaPhoto(
                        media=card.img,
                        caption=text,
                        parse_mode="HTML",
                    ),
                    reply_markup=keyboard,
                )
            else:
                await target.message.edit_text(
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            return
        except Exception:
            # Не получилось отредактировать — удаляем и шлём новое
            try:
                await target.message.delete()
            except Exception:
                pass

    # Отправляем новое сообщение
    msg = target.message if isinstance(target, CallbackQuery) else target

    if card.img:
        await msg.answer_photo(
            photo=card.img,
            caption=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    else:
        await msg.answer(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )


# ──────────────────────────────────────
# Точка входа: кнопка «Поиск»
# ──────────────────────────────────────

@router.message(F.text == "Поиск")
async def start_search(message: Message, state: FSMContext):
    """Нажатие кнопки 'Поиск' в главном меню."""
    user_id = message.from_user.id

    # Проверяем что анкета создана
    with SessionLocal() as db:
        from app.services.user_template_service import UserTemplateService
        template_svc = UserTemplateService()

        if not template_svc.profile_is_complete(db, user_id):
            await message.answer(
                "⚠️ Сначала создай анкету в разделе <b>Анкета</b>.",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(),
            )
            return

    # Показываем информацию и первую карточку
    views_left = search_service.get_views_left(user_id)

    if views_left <= 0:
        seconds = search_service.get_time_until_next(user_id)
        await message.answer(
            _no_views_text(seconds),
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(
        f"🔍 <b>Поиск тиммейтов</b>\n"
        f"Доступно просмотров: <b>{views_left}</b>",
        parse_mode="HTML",
    )

    # Загружаем первую карточку
    with SessionLocal() as db:
        card = search_service.get_next_card(db, user_id)

    if not card:
        await message.answer(
            "😔 Пока нет подходящих анкет. Попробуй позже!",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.set_state(SearchStates.browsing)
    await _send_card(message, card)


# ──────────────────────────────────────
# Лайк
# ──────────────────────────────────────

@router.callback_query(SearchStates.browsing, F.data == "search:like")
async def on_like(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    # Записываем лайк
    with SessionLocal() as db:
        search_service.on_like(db, user_id)

    await callback.answer("❤️ Лайк!")

    # Проверяем квоту
    views_left = search_service.get_views_left(user_id)

    if views_left <= 0:
        seconds = search_service.get_time_until_next(user_id)
        try:
            await callback.message.edit_text(
                _no_views_text(seconds), parse_mode="HTML"
            )
        except Exception:
            await callback.message.answer(
                _no_views_text(seconds), parse_mode="HTML"
            )
        await state.clear()
        return

    # Загружаем следующую карточку
    with SessionLocal() as db:
        card = search_service.get_next_card(db, user_id)

    if not card:
        try:
            await callback.message.edit_text(
                "📭 Подходящих анкет больше нет. Заходи позже!",
                parse_mode="HTML",
            )
        except Exception:
            await callback.message.answer(
                "📭 Подходящих анкет больше нет. Заходи позже!",
                parse_mode="HTML",
            )
        await state.clear()
        return

    await _send_card(callback, card, edit=True)


# ──────────────────────────────────────
# Дизлайк
# ──────────────────────────────────────

@router.callback_query(SearchStates.browsing, F.data == "search:dislike")
async def on_dislike(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    search_service.on_dislike(user_id)

    await callback.answer("👎")

    # Проверяем квоту
    views_left = search_service.get_views_left(user_id)

    if views_left <= 0:
        seconds = search_service.get_time_until_next(user_id)
        try:
            await callback.message.edit_text(
                _no_views_text(seconds), parse_mode="HTML"
            )
        except Exception:
            await callback.message.answer(
                _no_views_text(seconds), parse_mode="HTML"
            )
        await state.clear()
        return

    # Следующая карточка
    with SessionLocal() as db:
        card = search_service.get_next_card(db, user_id)

    if not card:
        try:
            await callback.message.edit_text(
                "📭 Подходящих анкет больше нет. Заходи позже!",
                parse_mode="HTML",
            )
        except Exception:
            await callback.message.answer(
                "📭 Подходящих анкет больше нет. Заходи позже!",
                parse_mode="HTML",
            )
        await state.clear()
        return

    await _send_card(callback, card, edit=True)


# ──────────────────────────────────────
# Вернуться к профилю
# ──────────────────────────────────────

@router.callback_query(SearchStates.browsing, F.data == "search:back_to_profile")
async def on_back_to_profile(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        "Возвращаю в главное меню.",
        reply_markup=main_menu_keyboard(),
    )