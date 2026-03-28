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
from app.services.content_service import ContentService


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
    show_rating: bool = False


@dataclass
class UserQuota:
    views_left: int = 10
    last_refill_time: float = field(default_factory=time.time)
    max_views: int = 10
    refill_interval: int = 3600
    unlimited: bool = False

    def refill(self) -> None:
        if self.unlimited:
            return
        if self.refill_interval <= 0:
            return
        now = time.time()
        elapsed = now - self.last_refill_time
        new_views = int(elapsed // self.refill_interval)
        if new_views > 0:
            self.views_left = min(self.max_views, self.views_left + new_views)
            self.last_refill_time += new_views * self.refill_interval

    def can_view(self) -> bool:
        if self.unlimited:
            return True
        self.refill()
        return self.views_left > 0

    def spend(self) -> bool:
        if self.unlimited:
            return True
        self.refill()
        if self.views_left <= 0:
            return False
        self.views_left -= 1
        return True

    def time_until_next(self) -> int:
        if self.unlimited:
            return 0
        self.refill()
        if self.views_left >= self.max_views:
            return 0
        if self.refill_interval <= 0:
            return 0
        now = time.time()
        next_refill = self.last_refill_time + self.refill_interval
        return max(0, int(next_refill - now))

    def refill_all(self) -> None:
        if self.unlimited:
            return
        self.views_left = self.max_views
        self.last_refill_time = time.time()


class SearchService:

    RATING_MIN: int = -100
    RATING_MAX: int = 100
    REVIEW_DELAY: int = 3600

    PLANS = {
        "free":  {"max_views": 10,  "refill_interval": 3600, "unlimited": False},
        "prime": {"max_views": 50,  "refill_interval": 3600, "unlimited": False},
        "gold":  {"max_views": 0,   "refill_interval": 0,    "unlimited": True},
    }

    def __init__(self, repo: UserRepo | None = None):
        self.repo = repo or UserRepo()
        self.content_service = ContentService(self.repo)
        self.bot: Bot | None = None
        self._quotas: dict[int, UserQuota] = {}
        self._seen: dict[int, set[int]] = {}
        self._current: dict[int, ProfileCard | None] = {}
        self._likes: dict[int, set[int]] = {}
        self._review_tasks: dict[tuple[int, int], asyncio.Task] = {}
        self._user_plans: dict[int, str] = {}

    def set_bot(self, bot: Bot) -> None:
        self.bot = bot

    # ─── Квоты с учётом подписки ─────────────

    def _get_quota(self, db: Session, user_id: int) -> UserQuota:
        current_plan = self.content_service.get_active_subscription(db, user_id)
        plan_config = self.PLANS.get(current_plan, self.PLANS["free"])

        old_plan = self._user_plans.get(user_id)

        if user_id not in self._quotas or old_plan != current_plan:
            quota = self._quotas.get(user_id)
            if quota is None:
                quota = UserQuota(
                    views_left=plan_config["max_views"],
                    max_views=plan_config["max_views"],
                    refill_interval=plan_config["refill_interval"],
                    unlimited=plan_config["unlimited"],
                )
                self._quotas[user_id] = quota
            else:
                quota.max_views = plan_config["max_views"]
                quota.refill_interval = plan_config["refill_interval"]
                quota.unlimited = plan_config["unlimited"]
                if current_plan != "free" and old_plan == "free":
                    if plan_config["unlimited"]:
                        quota.unlimited = True
                    else:
                        quota.views_left = plan_config["max_views"]

            self._user_plans[user_id] = current_plan

        return self._quotas[user_id]

    # ─── Oracle: входит в Prime и Gold ───────

    def _has_oracle(self, db: Session, user_id: int) -> bool:
        """
        Проверить есть ли функционал Oracle.
        Oracle входит в: отдельную покупку Oracle, Prime, Gold.
        """
        sub = self.content_service.get_active_subscription(db, user_id)
        if sub in ("prime", "gold"):
            return True
        return self.content_service.has_active_content(db, user_id, "oracle")

    # ─── Публичные методы ────────────────────

    def get_next_card(self, db: Session, user_id: int) -> ProfileCard | None:
        quota = self._get_quota(db, user_id)
        if not quota.can_view():
            return None

        has_oracle = self._has_oracle(db, user_id)

        card = self._pick_random_candidate(db, user_id, show_rating=has_oracle)
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

        if user_id not in self._likes:
            self._likes[user_id] = set()
        self._likes[user_id].add(target_id)

        is_mutual = self._is_mutual_like(user_id, target_id)

        if is_mutual:
            await self._send_match_notification(db, user_id, target_id)
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
        score = max(-5, min(5, score))
        user = self.repo.get_user_by_id(db, target_id)
        if not user:
            return
        current_rating = user.rating or 0
        new_rating = current_rating + score
        new_rating = max(self.RATING_MIN, min(self.RATING_MAX, new_rating))
        self.repo.update_user(db, target_id, rating=new_rating)

    def use_refresh(self, db: Session, user_id: int) -> bool:
        item = self.content_service.consume_usage(db, user_id, "refresh")
        if not item:
            return False
        quota = self._get_quota(db, user_id)
        quota.refill_all()
        self._seen.pop(user_id, None)
        return True

    def use_second_chance(self, db: Session, user_id: int) -> bool:
        item = self.content_service.consume_usage(db, user_id, "second_chance")
        if not item:
            return False
        self.repo.update_user(db, user_id, rating=0)
        return True

    def get_views_left(self, db: Session, user_id: int) -> int:
        quota = self._get_quota(db, user_id)
        quota.refill()
        return quota.views_left

    def get_time_until_next(self, db: Session, user_id: int) -> int:
        quota = self._get_quota(db, user_id)
        return quota.time_until_next()

    def is_unlimited(self, db: Session, user_id: int) -> bool:
        """Проверить, безлимитный ли поиск у пользователя."""
        quota = self._get_quota(db, user_id)
        return quota.unlimited

    def get_user_badge(self, db: Session, user_id: int) -> str:
        return self.content_service.get_subscription_badge(db, user_id)

    def reset_seen(self, user_id: int) -> None:
        self._seen.pop(user_id, None)

    # ─── Лайки и мэтчи ──────────────────────

    def _is_mutual_like(self, user_a: int, user_b: int) -> bool:
        a_likes_b = user_b in self._likes.get(user_a, set())
        b_likes_a = user_a in self._likes.get(user_b, set())
        return a_likes_b and b_likes_a

    # ─── Отложенная оценка ───────────────────

    def _schedule_review(self, user_a: int, user_b: int) -> None:
        key = (min(user_a, user_b), max(user_a, user_b))
        if key in self._review_tasks:
            return
        task = asyncio.create_task(
            self._delayed_review_notification(user_a, user_b)
        )
        self._review_tasks[key] = task

    async def _delayed_review_notification(
        self, user_a: int, user_b: int
    ) -> None:
        await asyncio.sleep(self.REVIEW_DELAY)
        key = (min(user_a, user_b), max(user_a, user_b))
        self._review_tasks.pop(key, None)
        if not self.bot:
            return
        await self._send_review_request(user_a, user_b)
        await self._send_review_request(user_b, user_a)

    async def _send_review_request(
        self, reviewer_id: int, target_id: int
    ) -> None:
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
        has_oracle = self._has_oracle(db, target_id)
        badge = self.get_user_badge(db, liker_id)
        text = self._format_like_notification(liker, badge, show_rating=has_oracle)
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

        badge_a = self.get_user_badge(db, user_a)
        badge_b = self.get_user_badge(db, user_b)

        has_oracle_a = self._has_oracle(db, user_a)
        has_oracle_b = self._has_oracle(db, user_b)

        text_for_a = self._format_match_notification(
            user_b_data, tg_username_b, badge_b, show_rating=has_oracle_a
        )
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
                    chat_id=user_a, text=text_for_a, parse_mode="HTML"
                )
        except Exception:
            pass

        text_for_b = self._format_match_notification(
            user_a_data, tg_username_a, badge_a, show_rating=has_oracle_b
        )
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
                    chat_id=user_b, text=text_for_b, parse_mode="HTML"
                )
        except Exception:
            pass

    # ─── Форматирование ─────────────────────

    @staticmethod
    def _format_like_notification(
        liker: User, badge: str, show_rating: bool = False
    ) -> str:
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

        rating_line = ""
        if show_rating:
            r = liker.rating if liker.rating is not None else 0
            rating_line = f"\n⭐ Рейтинг: <b>{r}</b>"

        return (
            "❤️ <b>Кому-то понравилась твоя анкета!</b>\n\n"
            f"{badge}\n"
            f"<b>👤 {liker.username or 'Игрок'}, {liker.age} лет</b>\n\n"
            f"🎮 <b>Игры:</b> {games_str}\n"
            f"🏷 <b>Роли:</b> {tags_str}\n\n"
            f"📝 {liker.description or 'Описание не указано'}"
            f"{rating_line}"
        )

    @staticmethod
    def _format_match_notification(
        user: User,
        tg_username: str | None,
        badge: str,
        show_rating: bool = False,
    ) -> str:
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

        rating_line = ""
        if show_rating:
            r = user.rating if user.rating is not None else 0
            rating_line = f"\n⭐ Рейтинг: <b>{r}</b>\n"

        return (
            "🎉 <b>У вас взаимная симпатия!</b>\n\n"
            f"{badge}\n"
            f"<b>👤 {user.username or 'Игрок'}, {user.age} лет</b>\n\n"
            f"🎮 <b>Игры:</b> {games_str}\n"
            f"🏷 <b>Роли:</b> {tags_str}\n\n"
            f"📝 {user.description or 'Описание не указано'}\n"
            f"{rating_line}\n"
            f"{contact}"
        )

    @staticmethod
    def _like_notification_keyboard(liker_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👎", callback_data=f"notify:dislike:{liker_id}"
                    ),
                    InlineKeyboardButton(
                        text="❤️", callback_data=f"notify:like:{liker_id}"
                    ),
                ],
            ]
        )

    @staticmethod
    def _review_keyboard(target_id: int) -> InlineKeyboardMarkup:
        row_negative = [
            InlineKeyboardButton(
                text=str(i), callback_data=f"review:{target_id}:{i}"
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
        return InlineKeyboardMarkup(inline_keyboard=[row_negative, row_positive])

    # ─── Подбор кандидатов ───────────────────

    def _pick_random_candidate(
        self, db: Session, user_id: int, show_rating: bool = False
    ) -> ProfileCard | None:
        user = self.repo.get_user_by_id(db, user_id)
        if not user or not user.games:
            return None

        user_games_set = set(user.games)
        seen_ids = self._seen.get(user_id, set())

        all_users: list[User] = self.repo.get_all_users(db, limit=10000, offset=0)

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
            show_rating=show_rating,
        )