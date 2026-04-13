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
from app.keyboards.keyboard import GAMES, GAME_TAGS, main_menu_keyboard, profile_menu_keyboard
from app.repo.repository import UserRepo
from app.services.content_service import ContentService
from app.services.service_search import SearchService
from app.services.user_template_service import UserTemplateService

router = Router()

search_service = SearchService()
content_service = ContentService(UserRepo())
template_service = UserTemplateService()


class SearchStates(StatesGroup):
    browsing = State()


# ──────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────

def _format_card(card) -> str:
    games_display = [GAMES.get(g, g) for g in (card.games or [])]
    games_str = ", ".join(games_display) if games_display else "не указаны"

    tags_display = []
    for tag_key in (card.tags or []):
        tag_name = tag_key
        for game_tags in GAME_TAGS.values():
            if tag_key in game_tags:
                tag_name = game_tags[tag_key]
                break
        tags_display.append(tag_name)
    tags_str = ", ".join(tags_display) if tags_display else "не указаны"

    rating_line = ""
    if card.show_rating:
        r = card.rating if card.rating is not None else 0
        rating_line = f"\n⭐ Рейтинг: <b>{r}</b>"

    return (
        f"<b>👤 {card.username or 'Игрок'}, {card.age} лет</b>\n\n"
        f"🎮 <b>Игры:</b> {games_str}\n"
        f"🏷 <b>Роли:</b> {tags_str}\n\n"
        f"📝 {card.description or 'Описание не указано'}"
        f"{rating_line}"
    )


def _card_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👎", callback_data="search:dislike"),
                InlineKeyboardButton(text="❤️", callback_data="search:like"),
            ],
            [
                InlineKeyboardButton(text="🚩 Репорт", callback_data="search:report"),
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
    if seconds_left <= 0:
        return "📭 Просмотры закончились. Попробуй ещё раз!"
    minutes = seconds_left // 60
    seconds = seconds_left % 60
    return (
        "⏳ <b>Просмотры закончились!</b>\n\n"
        f"Следующая анкета будет доступна через "
        f"<b>{minutes} мин {seconds} сек</b>.\n\n"
        "💡 Используй <b>Refresh</b> в разделе «Доп Контент», "
        "чтобы обновить поиск мгновенно!"
    )


def _games_limit_block_text(status: str, games_count: int, games_limit: int) -> str:
    if status == "free":
        return (
            "⚠️ <b>Поиск временно недоступен</b>\n\n"
            f"У тебя в анкете выбрано <b>{games_count}</b> игр, "
            f"но на бесплатном статусе доступна только <b>{games_limit}</b> игра.\n\n"
            "Зайди в <b>Анкета</b> и убери лишние игры, либо оформи Premium."
        )

    if status == "prime":
        return (
            "⚠️ <b>Поиск временно недоступен</b>\n\n"
            f"У тебя в анкете выбрано <b>{games_count}</b> игр, "
            f"но на Premium доступно только <b>{games_limit}</b> игры.\n\n"
            "Зайди в <b>Анкета</b> и убери лишние игры, либо оформи Gold."
        )

    return (
        "⚠️ <b>Поиск временно недоступен</b>\n\n"
        f"У тебя в анкете выбрано <b>{games_count}</b> игр, "
        f"но текущий лимит — <b>{games_limit}</b>."
    )


def _has_games_limit_violation(db, user_id: int) -> tuple[bool, str | None]:
    user_repo = UserRepo()
    user = user_repo.get_user_by_id(db, user_id)
    if not user:
        return False, None

    games = user.games or []
    games_limit = content_service.get_games_limit(db, user_id)

    if games_limit is None:
        return False, None

    if len(games) <= games_limit:
        return False, None

    status = content_service.get_subscription_status(db, user_id)
    return True, _games_limit_block_text(status, len(games), games_limit)


async def require_profile_for_search(target: Message | CallbackQuery) -> bool:
    if isinstance(target, Message):
        user_id = target.from_user.id
        sender = target
    else:
        user_id = target.from_user.id
        sender = target.message

    with SessionLocal() as db:
        has_profile = template_service.profile_is_complete(db, user_id)

    if has_profile:
        return True

    text = (
        "⚠️ <b>Сначала создай анкету</b>\n\n"
        "Поиск тиммейтов доступен только после заполнения анкеты.\n"
        "Сначала заполни профиль в разделе <b>Анкета</b>, а потом возвращайся в поиск."
    )

    await sender.answer(
        text,
        reply_markup=profile_menu_keyboard(has_profile=False),
        parse_mode="HTML",
    )

    if isinstance(target, CallbackQuery):
        await target.answer("Сначала создай анкету.", show_alert=True)

    return False


async def _send_card(
    target: Message | CallbackQuery, card, *, edit: bool = False
) -> None:
    text = _format_card(card)
    keyboard = _card_keyboard()

    if edit and isinstance(target, CallbackQuery):
        try:
            if card.img:
                await target.message.edit_media(
                    media=InputMediaPhoto(
                        media=card.img, caption=text, parse_mode="HTML"
                    ),
                    reply_markup=keyboard,
                )
            else:
                await target.message.edit_text(
                    text=text, reply_markup=keyboard, parse_mode="HTML"
                )
            return
        except Exception:
            try:
                await target.message.delete()
            except Exception:
                pass

    msg = target.message if isinstance(target, CallbackQuery) else target
    if card.img:
        await msg.answer_photo(
            photo=card.img,
            caption=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    else:
        await msg.answer(text=text, reply_markup=keyboard, parse_mode="HTML")


# ──────────────────────────────────────
# Кнопка «Поиск»
# ──────────────────────────────────────

@router.message(F.text == "Поиск")
async def start_search(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if not await require_profile_for_search(message):
        return

    with SessionLocal() as db:
        has_violation, violation_text = _has_games_limit_violation(db, user_id)
        if has_violation:
            await message.answer(
                violation_text,
                parse_mode="HTML",
                reply_markup=profile_menu_keyboard(has_profile=True),
            )
            return

        is_unlim = search_service.is_unlimited(db, user_id)
        views_left = search_service.get_views_left(db, user_id)

    if not is_unlim and views_left <= 0:
        with SessionLocal() as db:
            seconds = search_service.get_time_until_next(db, user_id)
        await message.answer(
            _no_views_text(seconds),
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
        return

    if is_unlim:
        status_text = "🔍 <b>Поиск тиммейтов</b>\n👑 Безлимитный поиск"
    else:
        status_text = (
            f"🔍 <b>Поиск тиммейтов</b>\n"
            f"Доступно просмотров: <b>{views_left}</b>"
        )

    await message.answer(status_text, parse_mode="HTML")

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
# Лайк из поиска
# ──────────────────────────────────────

@router.callback_query(SearchStates.browsing, F.data == "search:like")
async def on_like(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    if not await require_profile_for_search(callback):
        await state.clear()
        return

    with SessionLocal() as db:
        has_violation, violation_text = _has_games_limit_violation(db, user_id)
        if has_violation:
            await callback.answer("Поиск остановлен.", show_alert=True)
            try:
                await callback.message.edit_text(
                    violation_text,
                    parse_mode="HTML",
                    reply_markup=profile_menu_keyboard(has_profile=True),
                )
            except Exception:
                await callback.message.answer(
                    violation_text,
                    parse_mode="HTML",
                    reply_markup=profile_menu_keyboard(has_profile=True),
                )
            await state.clear()
            return

        await search_service.on_like(db, user_id)

    await callback.answer("❤️ Лайк!")

    with SessionLocal() as db:
        has_violation, violation_text = _has_games_limit_violation(db, user_id)
        if has_violation:
            try:
                await callback.message.edit_text(
                    violation_text,
                    parse_mode="HTML",
                    reply_markup=profile_menu_keyboard(has_profile=True),
                )
            except Exception:
                await callback.message.answer(
                    violation_text,
                    parse_mode="HTML",
                    reply_markup=profile_menu_keyboard(has_profile=True),
                )
            await state.clear()
            return

        is_unlim = search_service.is_unlimited(db, user_id)
        views_left = search_service.get_views_left(db, user_id)

    if not is_unlim and views_left <= 0:
        with SessionLocal() as db:
            seconds = search_service.get_time_until_next(db, user_id)
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
# Дизлайк из поиска
# ──────────────────────────────────────

@router.callback_query(SearchStates.browsing, F.data == "search:dislike")
async def on_dislike(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    if not await require_profile_for_search(callback):
        await state.clear()
        return

    search_service.on_dislike(user_id)
    await callback.answer("👎")

    with SessionLocal() as db:
        has_violation, violation_text = _has_games_limit_violation(db, user_id)
        if has_violation:
            try:
                await callback.message.edit_text(
                    violation_text,
                    parse_mode="HTML",
                    reply_markup=profile_menu_keyboard(has_profile=True),
                )
            except Exception:
                await callback.message.answer(
                    violation_text,
                    parse_mode="HTML",
                    reply_markup=profile_menu_keyboard(has_profile=True),
                )
            await state.clear()
            return

        is_unlim = search_service.is_unlimited(db, user_id)
        views_left = search_service.get_views_left(db, user_id)

    if not is_unlim and views_left <= 0:
        with SessionLocal() as db:
            seconds = search_service.get_time_until_next(db, user_id)
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


@router.callback_query(SearchStates.browsing, F.data == "search:report")
async def on_report(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    current_card = search_service.get_current_card(user_id)
    if not current_card:
        await callback.answer("Карточка не найдена.", show_alert=True)
        return

    with SessionLocal() as db:
        search_service.report_user(db, current_card.id)
    await callback.answer("Пользователь отправлен в репорт.")
    search_service.on_dislike(user_id)

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
        "Возвращаю в главное меню.", reply_markup=main_menu_keyboard()
    )


# ──────────────────────────────────────
# Лайк из УВЕДОМЛЕНИЯ
# ──────────────────────────────────────

@router.callback_query(F.data.startswith("notify:like:"))
async def on_notify_like(callback: CallbackQuery):
    user_id = callback.from_user.id
    target_id = int(callback.data.split(":")[2])

    with SessionLocal() as db:
        await search_service.on_like_from_notification(db, user_id, target_id)

    await callback.answer("❤️ Лайк!")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ──────────────────────────────────────
# Дизлайк из УВЕДОМЛЕНИЯ
# ──────────────────────────────────────

@router.callback_query(F.data.startswith("notify:dislike:"))
async def on_notify_dislike(callback: CallbackQuery):
    user_id = callback.from_user.id
    target_id = int(callback.data.split(":")[2])
    search_service.on_dislike_from_notification(user_id, target_id)
    await callback.answer("👎")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ──────────────────────────────────────
# Оценка напарника после мэтча
# ──────────────────────────────────────

@router.callback_query(F.data.startswith("review:"))
async def on_review(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌ Ошибка")
        return

    try:
        target_id = int(parts[1])
        score = int(parts[2])
    except ValueError:
        await callback.answer("❌ Ошибка")
        return

    if score < -5 or score > 5:
        await callback.answer("❌ Недопустимая оценка")
        return

    with SessionLocal() as db:
        search_service.apply_rating(db, target_id, score)

    if score > 0:
        emoji = "🟢"
        text = f"Вы поставили оценку <b>+{score}</b>"
    elif score < 0:
        emoji = "🔴"
        text = f"Вы поставили оценку <b>{score}</b>"
    else:
        emoji = "🟡"
        text = "Вы поставили оценку <b>0</b>"

    await callback.answer(f"{emoji} Оценка принята!")
    try:
        await callback.message.edit_text(
            f"✅ {text}. Спасибо за отзыв!", parse_mode="HTML"
        )
    except Exception:
        pass