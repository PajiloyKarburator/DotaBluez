from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.db.session import SessionLocal
from app.keyboards.keyboard import (
    GAME_TAGS,
    GAMES,
    back_to_menu_keyboard,
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
        f"Возраст: {user.age}\n"
        f"Фото: {'есть' if user.img else 'нет'}\n"
        f"О себе: {user.description or 'не указано'}\n"
        f"Игры: {games}\n"
        f"Теги: {tags}\n"
        f"Рейтинг: {user.rating if user.rating is not None else 'не указан'}"
    )


async def show_main_menu(target: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()

    text = (
        "Добро пожаловать в бот для поиска тиммейтов.\n\n"
        "Выбери нужный раздел:"
    )

    if isinstance(target, Message):
        await target.answer(text, reply_markup=main_menu_keyboard())
    else:
        await target.message.answer(text, reply_markup=main_menu_keyboard())
        await target.answer()


async def show_profile_menu(callback: CallbackQuery) -> None:
    with SessionLocal() as db:
        user = template_service.get_profile(db, callback.from_user.id)

    has_profile = bool(
        user
        and user.username
        and user.description
        and user.games
        and user.tags
    )

    text = "Раздел анкеты. Выбери действие:"
    await callback.message.answer(
        text,
        reply_markup=profile_menu_keyboard(has_profile=has_profile),
    )
    await callback.answer()


async def ask_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    current_name = data.get("username")

    text = "Напиши имя для анкеты."
    if current_name:
        text += f"\n\nТекущее значение: <b>{current_name}</b>"

    await state.set_state(TemplateStates.waiting_name)
    await message.answer(
        text,
        reply_markup=step_keyboard(back_callback="profile:menu"),
    )


async def ask_age(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    current_age = data.get("age")

    text = "Теперь укажи возраст числом."
    if current_age:
        text += f"\n\nТекущее значение: <b>{current_age}</b>"

    await state.set_state(TemplateStates.waiting_age)
    await message.answer(
        text,
        reply_markup=step_keyboard(back_callback="template:back:name"),
    )


async def ask_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    has_photo = bool(data.get("img"))

    text = "Отправь фото для анкеты."
    if has_photo:
        text += "\n\nСейчас фото уже выбрано."
    text += "\nМожно пропустить этот шаг."

    await state.set_state(TemplateStates.waiting_photo)
    await message.answer(
        text,
        reply_markup=step_keyboard(
            back_callback="template:back:age",
            skip_callback="template:skip:photo",
        ),
    )


async def ask_description(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    current_description = data.get("description")

    text = "Расскажи немного о себе."
    if current_description:
        text += f"\n\nТекущее описание:\n{current_description}"

    await state.set_state(TemplateStates.waiting_description)
    await message.answer(
        text,
        reply_markup=step_keyboard(back_callback="template:back:photo"),
    )


async def ask_games(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    selected_games = data.get("games", [])

    await state.set_state(TemplateStates.waiting_games)
    await message.answer(
        "Выбери игры. Можно несколько.\nКогда закончишь — нажми <b>Готово</b>.",
        reply_markup=games_keyboard(selected_games),
    )


async def ask_tags(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    selected_games = data.get("games", [])
    selected_tags = data.get("tags", [])

    if not selected_games:
        await message.answer("Сначала нужно выбрать хотя бы одну игру.")
        await ask_games(message, state)
        return

    await state.set_state(TemplateStates.waiting_tags)
    await message.answer(
        "Теперь выбери теги по выбранным играм. Можно несколько.",
        reply_markup=tags_keyboard(selected_games, selected_tags),
    )


async def ask_confirm(message: Message, state: FSMContext) -> None:
    data = await state.get_data()

    username = data.get("username", "не указано")
    age = data.get("age", "не указано")
    img = data.get("img")
    description = data.get("description", "не указано")
    games = ", ".join(data.get("games", [])) or "не указаны"
    tags = ", ".join(data.get("tags", [])) or "не указаны"

    text = (
        "Проверь анкету перед сохранением:\n\n"
        f"Имя: {username}\n"
        f"Возраст: {age}\n"
        f"Фото: {'есть' if img else 'нет'}\n"
        f"О себе: {description}\n"
        f"Игры: {games}\n"
        f"Теги: {tags}"
    )

    await state.set_state(TemplateStates.waiting_confirm)
    await message.answer(text, reply_markup=confirm_keyboard())


def collect_allowed_tags(selected_games: list[str]) -> set[str]:
    allowed_tags = set()
    for game in selected_games:
        allowed_tags.update(GAME_TAGS.get(game, {}).keys())
    return allowed_tags


# =========================
# START / MENU
# =========================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await show_main_menu(message, state)


@router.message(F.text == "Анкета")
async def profile_section(message: Message, state: FSMContext):
    await state.clear()

    with SessionLocal() as db:
        user = template_service.get_profile(db, message.from_user.id)

    has_profile = bool(
        user
        and user.username
        and user.description
        and user.games
        and user.tags
    )

    await message.answer(
        "Раздел анкеты. Выбери действие:",
        reply_markup=profile_menu_keyboard(has_profile=has_profile),
    )

# =========================
# @router.message(F.text == "Поиск")
# async def search_stub(message: Message):
#    await message.answer("Раздел поиска пока в разработке.", reply_markup=back_to_menu_keyboard())
# =========================

@router.message(F.text == "Подписка")
async def subscription_stub(message: Message):
    await message.answer("Раздел подписки пока в разработке.", reply_markup=back_to_menu_keyboard())


@router.message(F.text == "Помощь")
async def help_stub(message: Message):
    await message.answer(
        "Здесь ты можешь создать анкету и позже искать тиммейтов по играм и тегам.",
        reply_markup=back_to_menu_keyboard(),
    )


@router.callback_query(F.data == "menu:main")
async def menu_main_callback(callback: CallbackQuery, state: FSMContext):
    await show_main_menu(callback, state)


@router.callback_query(F.data == "profile:menu")
async def profile_menu_callback(callback: CallbackQuery):
    await show_profile_menu(callback)


# =========================
# ПРОСМОТР / УДАЛЕНИЕ АНКЕТЫ
# =========================

@router.callback_query(F.data == "profile:view")
async def view_profile(callback: CallbackQuery):
    with SessionLocal() as db:
        user = template_service.get_profile(db, callback.from_user.id)

    if not user:
        await callback.message.answer(
            "Анкета ещё не создана.",
            reply_markup=profile_menu_keyboard(has_profile=False),
        )
        await callback.answer()
        return

    if user.img:
        await callback.message.answer_photo(
            photo=user.img,
            caption=format_profile_text(user),
            reply_markup=profile_view_keyboard(),
        )
    else:
        await callback.message.answer(
            format_profile_text(user),
            reply_markup=profile_view_keyboard(),
        )

    await callback.answer()


@router.callback_query(F.data == "profile:delete")
async def delete_profile_ask(callback: CallbackQuery):
    await callback.message.answer(
        "Ты точно хочешь удалить анкету?",
        reply_markup=delete_confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "profile:delete:confirm")
async def delete_profile_confirm(callback: CallbackQuery, state: FSMContext):
    with SessionLocal() as db:
        template_service.delete_template(db, callback.from_user.id)

    await state.clear()
    await callback.message.answer("Анкета удалена.")
    await show_profile_menu(callback)


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
        "games": user.games if user and user.games else [],
        "tags": user.tags if user and user.tags else [],
        "rating": user.rating if user else None,
    }

    await state.set_data(initial_data)
    await callback.answer()
    await ask_name(callback.message, state)


# =========================
# BACK CALLBACKS
# =========================

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
# ШАГ 1 — ИМЯ
# =========================

@router.message(TemplateStates.waiting_name)
async def process_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()

    if len(name) < 2:
        await message.answer("Имя должно быть не короче 2 символов.")
        return

    if len(name) > 100:
        await message.answer("Имя слишком длинное. Максимум 100 символов.")
        return

    await state.update_data(username=name)
    await ask_age(message, state)


# =========================
# ШАГ 2 — ВОЗРАСТ
# =========================

@router.message(TemplateStates.waiting_age)
async def process_age(message: Message, state: FSMContext):
    text = (message.text or "").strip()

    if not text.isdigit():
        await message.answer("Возраст нужно отправить числом.")
        return

    age = int(text)
    if age < 10 or age > 99:
        await message.answer("Укажи реальный возраст от 10 до 99.")
        return

    await state.update_data(age=age)
    await ask_photo(message, state)


# =========================
# ШАГ 3 — ФОТО
# =========================

@router.message(TemplateStates.waiting_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(img=file_id)
    await ask_description(message, state)


@router.callback_query(F.data == "template:skip:photo")
async def skip_photo(callback: CallbackQuery, state: FSMContext):
    await state.update_data(img=None)
    await callback.answer()
    await ask_description(callback.message, state)


@router.message(TemplateStates.waiting_photo)
async def invalid_photo(message: Message):
    await message.answer("Отправь фото или нажми 'Пропустить'.")


# =========================
# ШАГ 4 — ОПИСАНИЕ
# =========================

@router.message(TemplateStates.waiting_description)
async def process_description(message: Message, state: FSMContext):
    description = (message.text or "").strip()

    if len(description) < 10:
        await message.answer("Описание слишком короткое. Напиши хотя бы 10 символов.")
        return

    if len(description) > 1000:
        await message.answer("Описание слишком длинное. Максимум 1000 символов.")
        return

    await state.update_data(description=description)
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
    selected_games = data.get("games", [])

    if game_key in selected_games:
        selected_games.remove(game_key)
    else:
        selected_games.append(game_key)

    # Если игры меняются, отсекаем теги, которых больше нет в доступных играх
    allowed_tags = collect_allowed_tags(selected_games)
    selected_tags = [tag for tag in data.get("tags", []) if tag in allowed_tags]

    await state.update_data(games=selected_games, tags=selected_tags)

    await callback.message.edit_reply_markup(
        reply_markup=games_keyboard(selected_games)
    )
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

    selected_tags = data.get("tags", [])
    if tag_value in selected_tags:
        selected_tags.remove(tag_value)
    else:
        selected_tags.append(tag_value)

    await state.update_data(tags=selected_tags)

    await callback.message.edit_reply_markup(
        reply_markup=tags_keyboard(selected_games, selected_tags)
    )
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

    await state.clear()
    await callback.message.answer("Анкета успешно сохранена ✅")
    await show_profile_menu(callback)