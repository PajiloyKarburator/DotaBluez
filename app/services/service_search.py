from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
import random

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session

from app.db.models import User
from app.repo.repository import UserRepo


@dataclass
class ProfileCard:
    """Одна карточка анкеты для показа."""
    id: int
    username: str | None
    age: int
    img: str | None
    description: str | None
    tags: list[str]
    games: list[str]
    rating: int | None


@dataclass
class UserQuota:
    views_left: int = 10
    last_refill_time: float = field(default_factory=time.time)

    MAX_VIEWS: int = 10
    REFILL_INTERVAL: int = 3600

    def refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill_time
        new_views = int(elapsed // self.REFILL_INTERVAL)
        if new_views > 0:
            self.views_left = min(self.MAX_VIEWS, self.views_left + new_views)
            self.last_refill_time += new_views * self.REFILL_INTERVAL

    def can_view(self) -> bool:
        self.refill()
        return self.views_left > 0

    def spend(self) -> bool:
        self.refill()
        if self.views_left <= 0:
            return False
        self.views_left -= 1
        return True

    def time_until_next(self) -> int:
        self.refill()
        if self.views_left >= self.MAX_VIEWS:
            return 0
        now = time.time()
        next_refill = self.last_refill_time + self.REFILL_INTERVAL
        return max(0, int(next_refill - now))


class SearchService:

    RATING_MIN: int = -100
    RATING_MAX: int = 100
    REVIEW_DELAY: int = 3600  # секунд (1 час)

    def __init__(self, repo: UserRepo | None = None):
        self.repo = repo or UserRepo()
        self.bot: Bot | None = None
        self._quotas: dict[int, UserQuota] = {}
        self._seen: dict[int, set[int]] = {}
        self._current: dict[int, ProfileCard | None] = {}
        self._likes: dict[int, set[int]] = {}

        # Хранилище запланированных оценок:
        # Чтобы не отправлять повторно
        # (user_a, user_b) → asyncio.Task
        self._review_tasks: dict[tuple[int, int], asyncio.Task] = {}

    def set_bot(self, bot: Bot) -> None:
        self.bot = bot

    # ─── Квоты ───────────────────────────────

    def _get_quota(self, user_id: int) -> UserQuota:
        if user_id not in self._quotas:
            self._quotas[user_id] = UserQuota()
        return self._quotas[user_id]

    # ─── Публичные методы ────────────────────

    def get_next_card(self, db: Session, user_id: int) -> ProfileCard | None:
        quota = self._get_quota(user_id)
        if not quota.can_view():
            return None

        card = self._pick_random_candidate(db, user_id)
        if card is None:
            return None

        quota.spend()

        if user_id not in self._seen:
            self._seen[user_id] = set()
        self._seen[user_id].add(card.id)

        self._current[user_id] = card
        return card

    def get_current_card(self, user_id: int) -> ProfileCard | None:
        return self._current.get(user_id)

    async def on_like(self, db: Session, user_id: int) -> None:
        card = self._current.get(user_id)
        if not card:
            return

        target_id = card.id

        # Записываем лайк (рейтинг НЕ меняем)
        if user_id not in self._likes:
            self._likes[user_id] = set()
        self._likes[user_id].add(target_id)

        # Проверяем взаимный лайк
        is_mutual = self._is_mutual_like(user_id, target_id)

        if is_mutual:
            await self._send_match_notification(db, user_id, target_id)
            # Запускаем отложенную оценку через 1 час
            self._schedule_review(user_id, target_id)
        else:
            await self._send_like_notification(db, user_id, target_id)

        self._current[user_id] = None

    def on_dislike(self, user_id: int) -> None:
        self._current[user_id] = None

    async def on_like_from_notification(
        self, db: Session, liker_id: int, target_id: int
    ) -> None:
        if liker_id not in self._likes:
            self._likes[liker_id] = set()
        self._likes[liker_id].add(target_id)

        is_mutual = self._is_mutual_like(liker_id, target_id)
        if is_mutual:
            await self._send_match_notification(db, liker_id, target_id)
            self._schedule_review(liker_id, target_id)

    def on_dislike_from_notification(self, liker_id: int, target_id: int) -> None:
        pass

    def apply_rating(self, db: Session, target_id: int, score: int) -> None:
        """
        Применить оценку к рейтингу пользователя.
        score: от -5 до 5
        Рейтинг ограничен [-100, 100].
        """
        # Проверяем допустимость оценки
        score = max(-5, min(5, score))

        user = self.repo.get_user_by_id(db, target_id)
        if not user:
            return

        current_rating = user.rating or 0
        new_rating = current_rating + score

        # Ограничиваем диапазон
        new_rating = max(self.RATING_MIN, min(self.RATING_MAX, new_rating))

        self.repo.update_user(db, target_id, rating=new_rating)

    def get_views_left(self, user_id: int) -> int:
        quota = self._get_quota(user_id)
        quota.refill()
        return quota.views_left

    def get_time_until_next(self, user_id: int) -> int:
        quota = self._get_quota(user_id)
        return quota.time_until_next()

    def reset_seen(self, user_id: int) -> None:
        self._seen.pop(user_id, None)

    # ─── Лайки и мэтчи ──────────────────────

    def _is_mutual_like(self, user_a: int, user_b: int) -> bool:
        a_likes_b = user_b in self._likes.get(user_a, set())
        b_likes_a = user_a in self._likes.get(user_b, set())
        return a_likes_b and b_likes_a

    # ─── Отложенная оценка ───────────────────

    def _schedule_review(self, user_a: int, user_b: int) -> None:
        """Запланировать отправку уведомлений об оценке через 1 час."""
        key = (min(user_a, user_b), max(user_a, user_b))

        # Не планируем повторно для той же пары
        if key in self._review_tasks:
            return

        task = asyncio.create_task(
            self._delayed_review_notification(user_a, user_b)
        )
        self._review_tasks[key] = task

    async def _delayed_review_notification(
        self, user_a: int, user_b: int
    ) -> None:
        """Подождать 1 час и отправить обоим предложение оценить напарника."""
        await asyncio.sleep(self.REVIEW_DELAY)

        key = (min(user_a, user_b), max(user_a, user_b))
        self._review_tasks.pop(key, None)

        if not self.bot:
            return

        # Отправляем user_a предложение оценить user_b
        await self._send_review_request(user_a, user_b)

        # Отправляем user_b предложение оценить user_a
        await self._send_review_request(user_b, user_a)

    async def _send_review_request(
        self, reviewer_id: int, target_id: int
    ) -> None:
        """Отправить одному пользователю предложение оценить другого."""
        if not self.bot:
            return

        from app.db.session import SessionLocal

        with SessionLocal() as db:
            target = self.repo.get_user_by_id(db, target_id)

        if not target:
            return

        target_name = target.username or "Игрок"

        text = (
            f"⏰ <b>Прошёл час с момента вашего мэтча!</b>\n\n"
            f"Оцените вашего напарника <b>{target_name}</b> "
            f"по шкале от <b>-5</b> до <b>5</b>:\n\n"
            f"🔴 -5 — ужасный опыт\n"
            f"🟡  0 — нормально\n"
            f"🟢 +5 — отличный напарник"
        )

        keyboard = self._review_keyboard(target_id)

        try:
            await self.bot.send_message(
                chat_id=reviewer_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        except Exception:
            pass

    # ─── Получение Telegram @username ────────

    async def _get_tg_username(self, user_id: int) -> str | None:
        if not self.bot:
            return None
        try:
            chat = await self.bot.get_chat(chat_id=user_id)
            return chat.username
        except Exception:
            return None

    # ─── Уведомления ────────────────────────

    async def _send_like_notification(
        self, db: Session, liker_id: int, target_id: int
    ) -> None:
        if not self.bot:
            return

        liker = self.repo.get_user_by_id(db, liker_id)
        if not liker:
            return

        text = self._format_like_notification(liker)
        keyboard = self._like_notification_keyboard(liker_id)

        try:
            if liker.img:
                await self.bot.send_photo(
                    chat_id=target_id,
                    photo=liker.img,
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            else:
                await self.bot.send_message(
                    chat_id=target_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
        except Exception:
            pass

    async def _send_match_notification(
        self, db: Session, user_a: int, user_b: int
    ) -> None:
        if not self.bot:
            return

        user_a_data = self.repo.get_user_by_id(db, user_a)
        user_b_data = self.repo.get_user_by_id(db, user_b)
        if not user_a_data or not user_b_data:
            return

        tg_username_a = await self._get_tg_username(user_a)
        tg_username_b = await self._get_tg_username(user_b)

        text_for_a = self._format_match_notification(user_b_data, tg_username_b)
        try:
            if user_b_data.img:
                await self.bot.send_photo(
                    chat_id=user_a,
                    photo=user_b_data.img,
                    caption=text_for_a,
                    parse_mode="HTML",
                )
            else:
                await self.bot.send_message(
                    chat_id=user_a,
                    text=text_for_a,
                    parse_mode="HTML",
                )
        except Exception:
            pass

        text_for_b = self._format_match_notification(user_a_data, tg_username_a)
        try:
            if user_a_data.img:
                await self.bot.send_photo(
                    chat_id=user_b,
                    photo=user_a_data.img,
                    caption=text_for_b,
                    parse_mode="HTML",
                )
            else:
                await self.bot.send_message(
                    chat_id=user_b,
                    text=text_for_b,
                    parse_mode="HTML",
                )
        except Exception:
            pass

    # ─── Форматирование ─────────────────────

    @staticmethod
    def _format_like_notification(liker: User) -> str:
        from app.keyboards.keyboard import GAMES, GAME_TAGS

        games_display = [GAMES.get(g, g) for g in (liker.games or [])]
        games_str = ", ".join(games_display) if games_display else "не указаны"

        tags_display = []
        for tag_key in (liker.tags or []):
            tag_name = tag_key
            for game_tags in GAME_TAGS.values():
                if tag_key in game_tags:
                    tag_name = game_tags[tag_key]
                    break
            tags_display.append(tag_name)
        tags_str = ", ".join(tags_display) if tags_display else "не указаны"

        return (
            "❤️ <b>Кому-то понравилась твоя анкета!</b>\n\n"
            f"<b>👤 {liker.username or 'Игрок'}, {liker.age} лет</b>\n\n"
            f"🎮 <b>Игры:</b> {games_str}\n"
            f"🏷 <b>Роли:</b> {tags_str}\n\n"
            f"📝 {liker.description or 'Описание не указано'}\n\n"
            f"⭐ Рейтинг: {liker.rating if liker.rating is not None else '—'}"
        )

    @staticmethod
    def _format_match_notification(user: User, tg_username: str | None) -> str:
        from app.keyboards.keyboard import GAMES, GAME_TAGS

        games_display = [GAMES.get(g, g) for g in (user.games or [])]
        games_str = ", ".join(games_display) if games_display else "не указаны"

        tags_display = []
        for tag_key in (user.tags or []):
            tag_name = tag_key
            for game_tags in GAME_TAGS.values():
                if tag_key in game_tags:
                    tag_name = game_tags[tag_key]
                    break
            tags_display.append(tag_name)
        tags_str = ", ".join(tags_display) if tags_display else "не указаны"

        if tg_username:
            contact = f"✉️ <b>Написать:</b> @{tg_username}"
        else:
            contact = (
                f"✉️ <b>Написать:</b> "
                f"<a href='tg://user?id={user.id}'>ссылка на профиль</a>"
            )

        return (
            "🎉 <b>У вас взаимная симпатия!</b>\n\n"
            f"<b>👤 {user.username or 'Игрок'}, {user.age} лет</b>\n\n"
            f"🎮 <b>Игры:</b> {games_str}\n"
            f"🏷 <b>Роли:</b> {tags_str}\n\n"
            f"📝 {user.description or 'Описание не указано'}\n\n"
            f"⭐ Рейтинг: {user.rating if user.rating is not None else '—'}\n\n"
            f"{contact}"
        )

    @staticmethod
    def _like_notification_keyboard(liker_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👎",
                        callback_data=f"notify:dislike:{liker_id}",
                    ),
                    InlineKeyboardButton(
                        text="❤️",
                        callback_data=f"notify:like:{liker_id}",
                    ),
                ],
            ]
        )

    @staticmethod
    def _review_keyboard(target_id: int) -> InlineKeyboardMarkup:
        """Клавиатура для оценки напарника от -5 до 5."""
        row_negative = [
            InlineKeyboardButton(
                text=str(i),
                callback_data=f"review:{target_id}:{i}",
            )
            for i in range(-5, 0)
        ]
        row_positive = [
            InlineKeyboardButton(
                text=f"+{i}" if i > 0 else str(i),
                callback_data=f"review:{target_id}:{i}",
            )
            for i in range(0, 6)
        ]

        return InlineKeyboardMarkup(
            inline_keyboard=[
                row_negative,
                row_positive,
            ]
        )

    # ─── Подбор кандидатов ───────────────────

    def _pick_random_candidate(
        self, db: Session, user_id: int
    ) -> ProfileCard | None:
        user = self.repo.get_user_by_id(db, user_id)
        if not user or not user.games:
            return None

        user_games_set = set(user.games)
        seen_ids = self._seen.get(user_id, set())

        all_users: list[User] = self.repo.get_all_users(
            db, limit=10000, offset=0
        )

        candidates: list[User] = []
        for u in all_users:
            if u.id == user_id:
                continue
            if u.id in seen_ids:
                continue
            if not u.username or not u.games or not u.description:
                continue
            candidate_games = set(u.games or [])
            if not user_games_set & candidate_games:
                continue
            candidates.append(u)

        if not candidates:
            return None

        chosen = random.choice(candidates)

        return ProfileCard(
            id=chosen.id,
            username=chosen.username,
            age=chosen.age,
            img=chosen.img,
            description=chosen.description,
            tags=chosen.tags or [],
            games=chosen.games or [],
            rating=chosen.rating,
        )