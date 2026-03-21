from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Машинные значения для БД / JSON
GAMES = {
    "csgo": "CS:GO",
    "dota2": "Dota 2",
    "valorant": "Valorant",
    "apex": "Apex Legends",
    "brawlstars": "Brawl Stars",
    "dbd": "Dead by Daylight",
}

GAME_TAGS = {
    "dota2": {
        "dota2_mid": "Мидер",
        "dota2_carry": "Керри",
        "dota2_support": "Саппорт",
        "dota2_offlane": "Оффлейн",
    },
    "csgo": {
        "csgo_rifler": "Rifler",
        "csgo_awper": "AWPer",
        "csgo_igl": "IGL",
        "csgo_support": "Support",
    },
    "valorant": {
        "valorant_duelist": "Duelist",
        "valorant_controller": "Controller",
        "valorant_initiator": "Initiator",
        "valorant_sentinel": "Sentinel",
    },
    "apex": {
        "apex_entry": "Entry",
        "apex_support": "Support",
        "apex_igl": "IGL",
        "apex_sniper": "Sniper",
    },
    "brawlstars": {
        "brawlstars_damage": "Damage Dealer",
        "brawlstars_support": "Support",
        "brawlstars_tank": "Tank",
        "brawlstars_control": "Control",
    },
    "dbd": {
        "dbd_survivor": "Survivor",
        "dbd_killer": "Killer",
        "dbd_chaser": "Chaser",
        "dbd_stealth": "Stealth",
    },
}


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Анкета"), KeyboardButton(text="Поиск")],
            [KeyboardButton(text="Подписка"), KeyboardButton(text="Помощь")],
        ],
        resize_keyboard=True,
    )


def profile_menu_keyboard(has_profile: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if has_profile:
        builder.button(text="Моя анкета", callback_data="profile:view")
        builder.button(text="Редактировать анкету", callback_data="profile:create")
        builder.button(text="Удалить анкету", callback_data="profile:delete")
    else:
        builder.button(text="Создать анкету", callback_data="profile:create")

    builder.button(text="Назад в меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад в меню", callback_data="menu:main")]
        ]
    )


def step_keyboard(
    *,
    back_callback: str,
    skip_callback: str | None = None,
    extra_callback: str | None = None,
    extra_text: str | None = None,
) -> InlineKeyboardMarkup:
    rows = []

    if skip_callback:
        rows.append([InlineKeyboardButton(text="Пропустить", callback_data=skip_callback)])

    if extra_callback and extra_text:
        rows.append([InlineKeyboardButton(text=extra_text, callback_data=extra_callback)])

    rows.append(
        [
            InlineKeyboardButton(text="Назад", callback_data=back_callback),
            InlineKeyboardButton(text="В меню", callback_data="menu:main"),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def games_keyboard(selected_games: list[str] | None = None) -> InlineKeyboardMarkup:
    selected_games = selected_games or []
    builder = InlineKeyboardBuilder()

    for game_key, game_title in GAMES.items():
        prefix = "✅ " if game_key in selected_games else ""
        builder.button(
            text=f"{prefix}{game_title}",
            callback_data=f"game:toggle:{game_key}",
        )

    builder.button(text="Готово", callback_data="game:done")
    builder.button(text="Назад", callback_data="template:back:description")
    builder.button(text="В меню", callback_data="menu:main")

    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def tags_keyboard(
    selected_games: list[str],
    selected_tags: list[str] | None = None,
) -> InlineKeyboardMarkup:
    selected_tags = selected_tags or []
    builder = InlineKeyboardBuilder()

    for game in selected_games:
        tags = GAME_TAGS.get(game, {})
        for tag_value, tag_title in tags.items():
            prefix = "✅ " if tag_value in selected_tags else ""
            builder.button(
                text=f"{prefix}{GAMES[game]} — {tag_title}",
                callback_data=f"tag:toggle:{tag_value}",
            )

    builder.button(text="Готово", callback_data="tag:done")
    builder.button(text="Назад", callback_data="template:back:games")
    builder.button(text="В меню", callback_data="menu:main")

    builder.adjust(1)
    return builder.as_markup()


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сохранить анкету", callback_data="template:save")],
            [InlineKeyboardButton(text="Назад", callback_data="template:back:tags")],
            [InlineKeyboardButton(text="В меню", callback_data="menu:main")],
        ]
    )


def profile_view_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Редактировать", callback_data="profile:create")],
            [InlineKeyboardButton(text="Удалить", callback_data="profile:delete")],
            [InlineKeyboardButton(text="Назад", callback_data="profile:menu")],
        ]
    )


def delete_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, удалить", callback_data="profile:delete:confirm"),
                InlineKeyboardButton(text="Отмена", callback_data="profile:menu"),
            ]
        ]
    )