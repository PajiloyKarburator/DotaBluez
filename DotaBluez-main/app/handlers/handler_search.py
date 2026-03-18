from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.services.service_search import SearchService, ProfileCard

router = Router()

# Инъецируется при подключении роутера в bot.py
search_service: SearchService = None  # noqa


class SearchStates(StatesGroup):
    """Состояния FSM для просмотра анкет."""
    browsing = State()


# ─────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────

def _build_card_keyboard(card: ProfileCard) -> InlineKeyboardMarkup:
    """Клавиатура под карточкой."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👎", callback_data=f"search_dislike:{card.id}"),
                InlineKeyboardButton(text="❤️", callback_data=f"search_like:{card.id}"),
            ],
            [
                InlineKeyboardButton(
                    text="⏭ Пропустить", callback_data=f"search_skip:{card.id}"
                ),
            ],
        ]
    )


def _format_card_text(card: ProfileCard) -> str:
    """Текст карточки."""
    games_str = ", ".join(card.games) if card.games else "не указаны"
    tags_str = " ".join(f"#{tag}" for tag in card.tags) if card.tags else ""

    text = (
        f"<b>👤 Игрок, {card.age} лет</b>\n\n"
        f"🎮 <b>Игры:</b> {games_str}\n\n"
        f"📝 {card.description}\n"
    )

    if tags_str:
        text += f"\n{tags_str}\n"

    text += f"\n❤️ {card.likes}"

    return text


async def _send_card(
    target: Message | CallbackQuery,
    card: ProfileCard,
    edit: bool = False,
):
    """Отправить или отредактировать карточку."""
    text = _format_card_text(card)
    keyboard = _build_card_keyboard(card)

    if edit and isinstance(target, CallbackQuery):
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
    else:
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
                text=text, reply_markup=keyboard, parse_mode="HTML"
            )


async def _show_empty(target: CallbackQuery | Message, state: FSMContext):
    """Сообщение когда анкеты закончились."""
    text = "📭 Анкеты закончились! Заходи позже."

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text=text, parse_mode="HTML")
    else:
        await target.answer(text=text, parse_mode="HTML")

    await state.clear()
    user_id = (
        target.from_user.id
        if isinstance(target, CallbackQuery)
        else target.from_user.id
    )
    search_service.end_session(user_id)


# ─────────────────────────────────────────────
# Хэндлеры команд
# ─────────────────────────────────────────────

@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext):
    """Команда /search — начать просмотр анкет."""
    user_id = message.from_user.id

    card = await search_service.start_session(user_id=user_id)

    if not card:
        await message.answer(
            "😔 Пока нет подходящих анкет. Попробуй позже!",
            parse_mode="HTML",
        )
        return

    await state.set_state(SearchStates.browsing)
    await _send_card(message, card)


@router.message(Command("stop_search"))
async def cmd_stop_search(message: Message, state: FSMContext):
    """Команда /stop_search — остановить просмотр."""
    user_id = message.from_user.id
    search_service.end_session(user_id)
    await state.clear()
    await message.answer("👋 Поиск остановлен.")


# ─────────────────────────────────────────────
# Хэндлеры свайпов
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("search_like:"), SearchStates.browsing)
async def on_like(callback: CallbackQuery, state: FSMContext):
    """Лайк."""
    user_id = callback.from_user.id

    next_card, is_match = await search_service.swipe(
        user_id=user_id, is_like=True
    )

    if is_match:
        await callback.answer("🎉 Взаимная симпатия! МЭТЧ!", show_alert=True)
    else:
        await callback.answer("❤️")

    if next_card:
        await _send_card(callback, next_card, edit=True)
    else:
        await _show_empty(callback, state)


@router.callback_query(F.data.startswith("search_dislike:"), SearchStates.browsing)
async def on_dislike(callback: CallbackQuery, state: FSMContext):
    """Дизлайк."""
    user_id = callback.from_user.id

    next_card, _ = await search_service.swipe(
        user_id=user_id, is_like=False
    )

    await callback.answer("👎")

    if next_card:
        await _send_card(callback, next_card, edit=True)
    else:
        await _show_empty(callback, state)


@router.callback_query(F.data.startswith("search_skip:"), SearchStates.browsing)
async def on_skip(callback: CallbackQuery, state: FSMContext):
    """Пропуск."""
    user_id = callback.from_user.id

    next_card = await search_service.skip(user_id)

    await callback.answer("⏭")

    if next_card:
        await _send_card(callback, next_card, edit=True)
    else:
        await _show_empty(callback, state)