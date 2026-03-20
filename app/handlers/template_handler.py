from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.db.session import SessionLocal
from app.keyboards.keyboard import (
    GAME_TAGS,
    GAMES,
    confirm_keyboard,
    delete_confirm_keyboard,
    games_keyboard,
    main_menu_keyboard,
    profile_menu_keyboard,
    profile_view_keyboard,
    step_keyboard,
    tags_keyboard,
)
from app.services.user_template_service import UserTemplateService

router = Router()
template_service = UserTemplateService()


class TemplateStates(StatesGroup):
    waiting_name = State()
    waiting_age = State()
    waiting_photo = State()
    waiting_description = State()
    waiting_games = State()
    waiting_tags = State()
    waiting_confirm = State()


# =========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================


def format_profile_text(user) -> str:
    games = ", ".join(user.games or []) if user.games else "не указаны"
    tags = ", ".join(user.tags or []) if user.tags else "не указаны"

    return (
        "🎮 <b>Твоя анкета</b>\n\n"
        f"Имя: {user.username or 'не указано'}\n"
        f"Возраст: {user.age if user.age is not None else 'не указан'}\n"
        f"Фото: {'есть' if user.img else 'нет'}\n"
        f"О себе: {user.description or 'не указано'}\n"
        f"Игры: {games}\n"
        f"Теги: {tags}\n"
        f"Рейтинг: {user.rating if user.rating is not None else 'не указан'}"
    )


def collect_allowed_tags(selected_games: list[str]) -> set[str]:
    allowed_tags = set()
    for game in selected_games:
        allowed_tags.update(GAME_TAGS.get(game, {}).keys())
    return allowed_tags


async def safe_delete_message(message: Message | None) -> None:
    if not message:
        return

    try:
        await message.delete()
    except TelegramBadRequest:
        pass


async def safe_delete_user_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


async def clear_form_message(state: FSMContext, bot, chat_id: int) -> None:
    data = await state.get_data()
    form_message_id = data.get("form_message_id")
    if not form_message_id:
        return

    try:
        await bot.delete_message(chat_id=chat_id, message_id=form_message_id)
    except TelegramBadRequest:
        pass

    await state.update_data(form_message_id=None)


async def hide_reply_keyboard(message: Message) -> None:
    service_message = await message.answer("✍️", reply_markup=ReplyKeyboardRemove())
    await safe_delete_message(service_message)


async def render_form_step(
    message: Message,
    state: FSMContext,
    *,
    text: str,
    reply_markup,
    form_state: State,
) -> None:
    await state.set_state(form_state)

    data = await state.get_data()
    form_message_id = data.get("form_message_id")

    if form_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=form_message_id,
                text=text,
                reply_markup=reply_markup,
            )
            return
        except TelegramBadRequest:
            pass

    sent_message = await message.answer(text, reply_markup=reply_markup)
    await state.update_data(form_message_id=sent_message.message_id)


async def show_main_menu(target: Message | CallbackQuery, state: FSMContext) -> None:
    if isinstance(target, Message):
        chat_id = target.chat.id
        bot = target.bot
    else:
        chat_id = target.message.chat.id
        bot = target.message.bot

    await clear_form_message(state, bot, chat_id)
    await state.clear()

    text = (
        "🎧 *Dota Blues* — turn your tilt into chill.\n\n"
        "Платформа для поиска тиммейтов нового уровня.\n"
        "Здесь ты находишь не просто игроков — а людей, с которыми игра действительно заходит.\n\n"
        "Никакого рандома, минимум токсика, только релевантные совпадения\n"
        "по играм, ролям и стилю общения.\n\n"
        "Создай анкету, отметь свои предпочтения и начни собирать команду,\n"
        "с которой хочется играть снова и снова.\n\n"
        "Хватит терпеть руин — играй в кайф.\n"
        "Выбери раздел ниже 👇"
    )

    if isinstance(target, Message):
        await target.answer(text, reply_markup=main_menu_keyboard())
    else:
        await target.message.answer(text, reply_markup=main_menu_keyboard())
        await target.answer()


async def show_profile_or_create(target: Message | CallbackQuery, state: FSMContext) -> None:
    if isinstance(target, Message):
        user_id = target.from_user.id
        message = target
    else:
        user_id = target.from_user.id
        message = target.message

    await clear_form_message(state, message.bot, message.chat.id)
    await state.clear()

    with SessionLocal() as db:
        user = template_service.get_profile(db, user_id)

    if user and user.username:
        if user.img:
            await message.answer_photo(
                photo=user.img,
                caption=format_profile_text(user),
                reply_markup=profile_view_keyboard(),
            )
        else:
            await message.answer(
                format_profile_text(user),
                reply_markup=profile_view_keyboard(),
            )
    else:
        await message.answer(
            "У тебя пока нет анкеты. Давай создадим её 👇",
            reply_markup=profile_menu_keyboard(has_profile=False),
        )

    if isinstance(target, CallbackQuery):
        await target.answer()


async def ask_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    current_name = data.get("username")

    text = (
        "🎮 Давай настроим анкету.\n\n"
        "Шаг 1/6\n"
        "Как тебя указать в анкете?"
    )
    if current_name:
        text += (
            f"\n\nТекущее значение: <b>{current_name}</b>"
            "\nНажми «Далее», если не хочешь менять."
        )

    await render_form_step(
        message,
        state,
        text=text,
        reply_markup=step_keyboard(
            back_callback="template:back:profile",
            next_callback="template:next:name" if current_name else None,
        ),
        form_state=TemplateStates.waiting_name,
    )


async def ask_age(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    current_age = data.get("age")

    text = (
        "📌 Шаг 2/6\n"
        "Теперь укажи возраст числом.\n\n"
        "Это поможет сделать анкету понятнее для других игроков."
    )
    if current_age is not None:
        text += (
            f"\n\nТекущее значение: <b>{current_age}</b>"
            "\nНажми «Далее», если не хочешь менять."
        )

    await render_form_step(
        message,
        state,
        text=text,
        reply_markup=step_keyboard(
            back_callback="template:back:name",
            next_callback="template:next:age" if current_age is not None else None,
        ),
        form_state=TemplateStates.waiting_age,
    )


async def ask_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    has_photo = bool(data.get("img"))

    text = (
        "🖼 Шаг 3/6\n"
        "Отправь фото для анкеты.\n\n"
        "С фото профиль выглядит живее и вызывает больше доверия."
    )

    if has_photo:
        text += "\n\nСейчас фото уже выбрано.\nНажми «Далее», если хочешь оставить его."
    else:
        text += "\n\nЕсли не хочешь добавлять фото сейчас, этот шаг можно пропустить."

    await render_form_step(
        message,
        state,
        text=text,
        reply_markup=step_keyboard(
            back_callback="template:back:age",
            next_callback="template:next:photo" if has_photo else None,
            skip_callback="template:skip:photo" if not has_photo else None,
        ),
        form_state=TemplateStates.waiting_photo,
    )


async def ask_description(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    current_description = data.get("description")

    text = (
        "✍️ Шаг 4/6\n"
        "Расскажи немного о себе.\n\n"
        "Например: во что играешь, какой у тебя стиль игры, кого ищешь и как предпочитаешь общаться."
    )
    if current_description:
        text += (
            f"\n\nТекущее описание:\n{current_description}"
            "\n\nНажми «Далее», если не хочешь менять."
        )

    await render_form_step(
        message,
        state,
        text=text,
        reply_markup=step_keyboard(
            back_callback="template:back:photo",
            next_callback="template:next:description" if current_description else None,
        ),
        form_state=TemplateStates.waiting_description,
    )


async def ask_games(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    selected_games = data.get("games", [])

    text = (
        "🎯 Шаг 5/6\n"
        "Выбери игры, для которых хочешь найти тиммейтов.\n"
        "Можно выбрать несколько.\n\n"
        "Когда закончишь — нажми <b>Далее</b>."
    )

    if selected_games:
        current_games = ", ".join(GAMES.get(game, game) for game in selected_games)
        text += f"\n\nСейчас выбрано: <b>{current_games}</b>"

    await render_form_step(
        message,
        state,
        text=text,
        reply_markup=games_keyboard(selected_games),
        form_state=TemplateStates.waiting_games,
    )


async def ask_tags(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    selected_games = data.get("games", [])
    selected_tags = data.get("tags", [])

    if not selected_games:
        await ask_games(message, state)
        return

    text = (
        "🧩 Шаг 6/6\n"
        "Теперь выбери теги и роли по выбранным играм.\n"
        "Можно несколько.\n\n"
        "Это поможет подобрать тебе более подходящих тиммейтов."
    )

    if selected_tags:
        current_tags = []
        for game in selected_games:
            tags_map = GAME_TAGS.get(game, {})
            for tag_value in selected_tags:
                if tag_value in tags_map:
                    current_tags.append(f"{GAMES[game]} — {tags_map[tag_value]}")
        if current_tags:
            text += "\n\nСейчас выбрано:\n" + "\n".join(f"• {tag}" for tag in current_tags)

    await render_form_step(
        message,
        state,
        text=text,
        reply_markup=tags_keyboard(selected_games, selected_tags),
        form_state=TemplateStates.waiting_tags,
    )


async def ask_confirm(message: Message, state: FSMContext) -> None:
    data = await state.get_data()

    username = data.get("username", "не указано")
    age = data.get("age", "не указано")
    img = data.get("img")
    description = data.get("description", "не указано")

    games_values = data.get("games", [])
    games_titles = [GAMES.get(game, game) for game in games_values]
    games = ", ".join(games_titles) if games_titles else "не указаны"

    tags_values = data.get("tags", [])
    tag_titles = []
    for game in games_values:
        game_tags = GAME_TAGS.get(game, {})
        for tag_value in tags_values:
            if tag_value in game_tags:
                tag_titles.append(f"{GAMES[game]} — {game_tags[tag_value]}")
    tags = ", ".join(tag_titles) if tag_titles else "не указаны"

    text = (
        "✅ Почти готово!\n\n"
        "Проверь анкету перед сохранением:\n\n"
        f"Имя: {username}\n"
        f"Возраст: {age}\n"
        f"Фото: {'есть' if img else 'нет'}\n"
        f"О себе: {description}\n"
        f"Игры: {games}\n"
        f"Теги: {tags}\n\n"
        "Если всё устраивает — сохраняй анкету."
    )

    await render_form_step(
        message,
        state,
        text=text,
        reply_markup=confirm_keyboard(),
        form_state=TemplateStates.waiting_confirm,
    )


# =========================
# ОБЩИЕ CALLBACKS
# =========================


@router.callback_query(F.data == "menu:main")
async def menu_main_callback(callback: CallbackQuery, state: FSMContext):
    await show_main_menu(callback, state)


@router.callback_query(F.data == "profile:menu")
async def profile_menu_callback(callback: CallbackQuery, state: FSMContext):
    await clear_form_message(state, callback.message.bot, callback.message.chat.id)
    await state.clear()

    with SessionLocal() as db:
        user = template_service.get_profile(db, callback.from_user.id)

    has_profile = bool(user and user.username)

    if has_profile:
        await callback.message.answer(
            "Что хочешь сделать с анкетой?",
            reply_markup=profile_menu_keyboard(has_profile=True),
        )
    else:
        await callback.message.answer(
            "У тебя пока нет анкеты. Давай создадим её 👇",
            reply_markup=profile_menu_keyboard(has_profile=False),
        )

    await callback.answer()


@router.callback_query(F.data == "template:cancel")
async def cancel_template_editing(callback: CallbackQuery, state: FSMContext):
    await clear_form_message(state, callback.message.bot, callback.message.chat.id)
    await state.clear()
    await callback.answer("Редактирование отменено")
    await show_profile_or_create(callback, state)


# =========================
# ПРОСМОТР / УДАЛЕНИЕ АНКЕТЫ
# =========================


@router.callback_query(F.data == "profile:view")
async def view_profile(callback: CallbackQuery, state: FSMContext):
    await show_profile_or_create(callback, state)


@router.callback_query(F.data == "profile:delete")
async def delete_profile_ask(callback: CallbackQuery):
    await callback.message.answer(
        "Ты точно хочешь удалить анкету?\n\n"
        "После удаления её нужно будет заполнять заново.",
        reply_markup=delete_confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "profile:delete:confirm")
async def delete_profile_confirm(callback: CallbackQuery, state: FSMContext):
    with SessionLocal() as db:
        template_service.delete_template(db, callback.from_user.id)

    await clear_form_message(state, callback.message.bot, callback.message.chat.id)
    await state.clear()

    await callback.message.answer("Анкета удалена.")
    await callback.message.answer(
        "У тебя пока нет анкеты. Давай создадим её 👇",
        reply_markup=profile_menu_keyboard(has_profile=False),
    )
    await callback.answer()


# =========================
# СОЗДАНИЕ / РЕДАКТИРОВАНИЕ АНКЕТЫ
# =========================


@router.callback_query(F.data == "profile:create")
async def start_template_creation(callback: CallbackQuery, state: FSMContext):
    with SessionLocal() as db:
        user = template_service.get_profile(db, callback.from_user.id)

    initial_data = {
        "username": user.username if user else None,
        "age": user.age if user else None,
        "img": user.img if user else None,
        "description": user.description if user else None,
        "games": list(user.games) if user and user.games else [],
        "tags": list(user.tags) if user and user.tags else [],
        "rating": user.rating if user else None,
        "form_message_id": None,
        "is_editing": bool(user and user.username),
    }

    await state.set_data(initial_data)
    await hide_reply_keyboard(callback.message)
    await callback.answer()
    await ask_name(callback.message, state)


# =========================
# BACK CALLBACKS
# =========================


@router.callback_query(F.data == "template:back:profile")
async def back_to_profile_from_edit(callback: CallbackQuery, state: FSMContext):
    await clear_form_message(state, callback.message.bot, callback.message.chat.id)
    await state.clear()
    await callback.answer()
    await show_profile_or_create(callback, state)


@router.callback_query(F.data == "template:back:name")
async def back_to_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await ask_name(callback.message, state)


@router.callback_query(F.data == "template:back:age")
async def back_to_age(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await ask_age(callback.message, state)


@router.callback_query(F.data == "template:back:photo")
async def back_to_photo(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await ask_photo(callback.message, state)


@router.callback_query(F.data == "template:back:description")
async def back_to_description(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await ask_description(callback.message, state)


@router.callback_query(F.data == "template:back:games")
async def back_to_games(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await ask_games(callback.message, state)


@router.callback_query(F.data == "template:back:tags")
async def back_to_tags(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await ask_tags(callback.message, state)


# =========================
# NEXT CALLBACKS
# =========================


@router.callback_query(F.data == "template:next:name")
async def next_from_name(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("username"):
        await callback.answer("Сначала укажи имя.", show_alert=True)
        return

    await callback.answer()
    await ask_age(callback.message, state)


@router.callback_query(F.data == "template:next:age")
async def next_from_age(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("age") is None:
        await callback.answer("Сначала укажи возраст.", show_alert=True)
        return

    await callback.answer()
    await ask_photo(callback.message, state)


@router.callback_query(F.data == "template:next:photo")
async def next_from_photo(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await ask_description(callback.message, state)


@router.callback_query(F.data == "template:next:description")
async def next_from_description(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("description"):
        await callback.answer("Сначала добавь описание.", show_alert=True)
        return

    await callback.answer()
    await ask_games(callback.message, state)


# =========================
# ШАГ 1 — ИМЯ
# =========================


@router.message(TemplateStates.waiting_name)
async def process_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()

    if len(name) < 2:
        await safe_delete_user_message(message)
        await render_form_step(
            message,
            state,
            text=(
                "Имя получилось слишком коротким.\n\n"
                "Напиши, как тебя лучше указать в анкете. Минимум 2 символа."
            ),
            reply_markup=step_keyboard(
                back_callback="template:back:profile",
                next_callback="template:next:name" if (await state.get_data()).get("username") else None,
            ),
            form_state=TemplateStates.waiting_name,
        )
        return

    if len(name) > 100:
        await safe_delete_user_message(message)
        await render_form_step(
            message,
            state,
            text=(
                "Имя получилось слишком длинным.\n\n"
                "Максимум — 100 символов. Попробуй написать короче."
            ),
            reply_markup=step_keyboard(
                back_callback="template:back:profile",
                next_callback="template:next:name" if (await state.get_data()).get("username") else None,
            ),
            form_state=TemplateStates.waiting_name,
        )
        return

    await state.update_data(username=name)
    await safe_delete_user_message(message)
    await ask_age(message, state)


# =========================
# ШАГ 2 — ВОЗРАСТ
# =========================


@router.message(TemplateStates.waiting_age)
async def process_age(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    data = await state.get_data()
    current_age = data.get("age")

    if not text.isdigit():
        await safe_delete_user_message(message)
        await render_form_step(
            message,
            state,
            text=(
                "Возраст нужно отправить числом.\n\n"
                "Например: 18"
            ),
            reply_markup=step_keyboard(
                back_callback="template:back:name",
                next_callback="template:next:age" if current_age is not None else None,
            ),
            form_state=TemplateStates.waiting_age,
        )
        return

    age = int(text)
    if age < 10 or age > 99:
        await safe_delete_user_message(message)
        await render_form_step(
            message,
            state,
            text=(
                "Укажи возраст от 10 до 99 лет.\n\n"
                "Теперь введи возраст числом."
            ),
            reply_markup=step_keyboard(
                back_callback="template:back:name",
                next_callback="template:next:age" if current_age is not None else None,
            ),
            form_state=TemplateStates.waiting_age,
        )
        return

    await state.update_data(age=age)
    await safe_delete_user_message(message)
    await ask_photo(message, state)


# =========================
# ШАГ 3 — ФОТО
# =========================


@router.message(TemplateStates.waiting_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(img=file_id)
    await safe_delete_user_message(message)
    await ask_description(message, state)


@router.callback_query(F.data == "template:skip:photo")
async def skip_photo(callback: CallbackQuery, state: FSMContext):
    await state.update_data(img=None)
    await callback.answer()
    await ask_description(callback.message, state)


@router.message(TemplateStates.waiting_photo)
async def invalid_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    has_photo = bool(data.get("img"))

    await safe_delete_user_message(message)
    await render_form_step(
        message,
        state,
        text=(
            "На этом шаге нужно отправить фото.\n\n"
            "Либо нажми «Далее», чтобы оставить текущее фото, "
            "либо «Пропустить», если хочешь сохранить анкету без фото."
        )
        if has_photo
        else (
            "На этом шаге нужно отправить фото.\n\n"
            "Или нажми «Пропустить», если пока не хочешь его добавлять."
        ),
        reply_markup=step_keyboard(
            back_callback="template:back:age",
            next_callback="template:next:photo" if has_photo else None,
            skip_callback="template:skip:photo" if not has_photo else None,
        ),
        form_state=TemplateStates.waiting_photo,
    )


# =========================
# ШАГ 4 — ОПИСАНИЕ
# =========================


@router.message(TemplateStates.waiting_description)
async def process_description(message: Message, state: FSMContext):
    description = (message.text or "").strip()
    data = await state.get_data()
    current_description = data.get("description")

    if len(description) < 10:
        await safe_delete_user_message(message)
        await render_form_step(
            message,
            state,
            text=(
                "Описание слишком короткое.\n\n"
                "Напиши хотя бы 10 символов о себе: например, кого ищешь, как играешь или когда обычно онлайн."
            ),
            reply_markup=step_keyboard(
                back_callback="template:back:photo",
                next_callback="template:next:description" if current_description else None,
            ),
            form_state=TemplateStates.waiting_description,
        )
        return

    if len(description) > 1000:
        await safe_delete_user_message(message)
        await render_form_step(
            message,
            state,
            text=(
                "Описание слишком длинное.\n\n"
                "Максимум — 1000 символов. Попробуй сократить текст."
            ),
            reply_markup=step_keyboard(
                back_callback="template:back:photo",
                next_callback="template:next:description" if current_description else None,
            ),
            form_state=TemplateStates.waiting_description,
        )
        return

    await state.update_data(description=description)
    await safe_delete_user_message(message)
    await ask_games(message, state)


# =========================
# ШАГ 5 — ИГРЫ
# =========================


@router.callback_query(TemplateStates.waiting_games, F.data.startswith("game:toggle:"))
async def toggle_game(callback: CallbackQuery, state: FSMContext):
    game_key = callback.data.split(":")[-1]
    if game_key not in GAMES:
        await callback.answer("Неизвестная игра", show_alert=True)
        return

    data = await state.get_data()
    selected_games = list(data.get("games", []))

    if game_key in selected_games:
        selected_games.remove(game_key)
    else:
        selected_games.append(game_key)

    allowed_tags = collect_allowed_tags(selected_games)
    selected_tags = [tag for tag in data.get("tags", []) if tag in allowed_tags]

    await state.update_data(games=selected_games, tags=selected_tags)

    try:
        await callback.message.edit_reply_markup(
            reply_markup=games_keyboard(selected_games)
        )
    except TelegramBadRequest:
        pass

    await callback.answer()


@router.callback_query(TemplateStates.waiting_games, F.data == "game:done")
async def games_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_games = data.get("games", [])

    if not selected_games:
        await callback.answer("Выбери хотя бы одну игру.", show_alert=True)
        return

    await callback.answer()
    await ask_tags(callback.message, state)


# =========================
# ШАГ 6 — ТЕГИ
# =========================


@router.callback_query(TemplateStates.waiting_tags, F.data.startswith("tag:toggle:"))
async def toggle_tag(callback: CallbackQuery, state: FSMContext):
    tag_value = callback.data.split(":")[-1]

    data = await state.get_data()
    selected_games = data.get("games", [])
    allowed_tags = collect_allowed_tags(selected_games)

    if tag_value not in allowed_tags:
        await callback.answer("Этот тег недоступен для выбранных игр.", show_alert=True)
        return

    selected_tags = list(data.get("tags", []))
    if tag_value in selected_tags:
        selected_tags.remove(tag_value)
    else:
        selected_tags.append(tag_value)

    await state.update_data(tags=selected_tags)

    try:
        await callback.message.edit_reply_markup(
            reply_markup=tags_keyboard(selected_games, selected_tags)
        )
    except TelegramBadRequest:
        pass

    await callback.answer()


@router.callback_query(TemplateStates.waiting_tags, F.data == "tag:done")
async def tags_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_tags = data.get("tags", [])

    if not selected_tags:
        await callback.answer("Выбери хотя бы один тег.", show_alert=True)
        return

    await callback.answer()
    await ask_confirm(callback.message, state)


# =========================
# ШАГ 7 — СОХРАНЕНИЕ
# =========================


@router.callback_query(TemplateStates.waiting_confirm, F.data == "template:save")
async def save_template(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    with SessionLocal() as db:
        template_service.create_template(
            db,
            user_id=callback.from_user.id,
            username=data.get("username"),
            age=data.get("age"),
            img=data.get("img"),
            description=data.get("description"),
            tags=data.get("tags", []),
            games=data.get("games", []),
            rating=data.get("rating"),
        )

    await clear_form_message(state, callback.message.bot, callback.message.chat.id)
    await state.clear()

    await callback.message.answer("Анкета успешно сохранена ✅")
    await callback.answer()
    await show_profile_or_create(callback, state)