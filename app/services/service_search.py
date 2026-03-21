from __future__ import annotations

import time
from dataclasses import dataclass, field
import random

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
    """
    Квота просмотров одного пользователя.

    Логика:
    - Начальный запас: 10 просмотров.
    - Каждый час реального времени добавляется 1 просмотр.
    - Максимум можно накопить 10.
    - При каждом свайпе (лайк/дизлайк) тратится 1 просмотр.
    """
    views_left: int = 10
    last_refill_time: float = field(default_factory=time.time)

    # Константы
    MAX_VIEWS: int = 10
    REFILL_INTERVAL: int = 3600  # секунд (1 час)

    def refill(self) -> None:
        """Начислить просмотры за прошедшее время."""
        now = time.time()
        elapsed = now - self.last_refill_time
        new_views = int(elapsed // self.REFILL_INTERVAL)

        if new_views > 0:
            self.views_left = min(self.MAX_VIEWS, self.views_left + new_views)
            # Сдвигаем время только на целое кол-во интервалов,
            # чтобы «остаток» минут не терялся
            self.last_refill_time += new_views * self.REFILL_INTERVAL

    def can_view(self) -> bool:
        """Есть ли доступные просмотры."""
        self.refill()
        return self.views_left > 0

    def spend(self) -> bool:
        """Потратить 1 просмотр. Возвращает True если успешно."""
        self.refill()
        if self.views_left <= 0:
            return False
        self.views_left -= 1
        return True

    def time_until_next(self) -> int:
        """Секунд до следующего начисления."""
        self.refill()
        if self.views_left >= self.MAX_VIEWS:
            return 0
        now = time.time()
        next_refill = self.last_refill_time + self.REFILL_INTERVAL
        return max(0, int(next_refill - now))


class SearchService:
    """
    Сервис поиска анкет.

    - Показывает случайные анкеты с совпадением хотя бы по 1 игре.
    - Не показывает повторно уже просмотренные анкеты (в рамках сессии).
    - Контролирует квоту: 10 просмотров, потом 1 в час.
    """

    def __init__(self, repo: UserRepo | None = None):
        self.repo = repo or UserRepo()

        # user_id → UserQuota  (квоты просмотров)
        self._quotas: dict[int, UserQuota] = {}

        # user_id → set[int]  (ID уже показанных анкет)
        self._seen: dict[int, set[int]] = {}

        # user_id → ProfileCard | None  (текущая показанная карточка)
        self._current: dict[int, ProfileCard | None] = {}

    # ─── Квоты ───────────────────────────────

    def _get_quota(self, user_id: int) -> UserQuota:
        if user_id not in self._quotas:
            self._quotas[user_id] = UserQuota()
        return self._quotas[user_id]

    # ─── Публичные методы ────────────────────

    def get_next_card(self, db: Session, user_id: int) -> ProfileCard | None:
        """
        Получить следующую случайную анкету.
        Возвращает None если нет кандидатов или кончилась квота.
        """
        quota = self._get_quota(user_id)

        if not quota.can_view():
            return None

        card = self._pick_random_candidate(db, user_id)

        if card is None:
            return None

        # Тратим просмотр и запоминаем
        quota.spend()

        if user_id not in self._seen:
            self._seen[user_id] = set()
        self._seen[user_id].add(card.id)

        self._current[user_id] = card

        return card

    def get_current_card(self, user_id: int) -> ProfileCard | None:
        """Текущая карточка (без траты просмотра)."""
        return self._current.get(user_id)

    def on_like(self, db: Session, user_id: int) -> None:
        """Обработка лайка — увеличиваем рейтинг target."""
        card = self._current.get(user_id)
        if not card:
            return

        target = self.repo.get_user_by_id(db, card.id)
        if target:
            new_rating = (target.rating or 0) + 1
            self.repo.update_user(db, card.id, rating=new_rating)

        self._current[user_id] = None

    def on_dislike(self, user_id: int) -> None:
        """Обработка дизлайка — просто убираем текущую карточку."""
        self._current[user_id] = None

    def get_views_left(self, user_id: int) -> int:
        """Сколько просмотров осталось."""
        quota = self._get_quota(user_id)
        quota.refill()
        return quota.views_left

    def get_time_until_next(self, user_id: int) -> int:
        """Секунд до следующего начисления."""
        quota = self._get_quota(user_id)
        return quota.time_until_next()

    def reset_seen(self, user_id: int) -> None:
        """Сбросить список просмотренных (если нужно)."""
        self._seen.pop(user_id, None)

    # ─── Внутренняя логика ───────────────────

    def _pick_random_candidate(
        self, db: Session, user_id: int
    ) -> ProfileCard | None:
        """Выбрать случайного кандидата с совпадением по играм."""

        # Профиль текущего пользователя
        user = self.repo.get_user_by_id(db, user_id)
        if not user or not user.games:
            return None

        user_games_set = set(user.games)
        seen_ids = self._seen.get(user_id, set())

        # Загружаем всех пользователей
        all_users: list[User] = self.repo.get_all_users(db, limit=10000, offset=0)

        # Фильтруем
        candidates: list[User] = []
        for u in all_users:
            # Не показываем себя
            if u.id == user_id:
                continue

            # Не показываем уже просмотренных
            if u.id in seen_ids:
                continue

            # Анкета должна быть заполнена
            if not u.username or not u.games or not u.description:
                continue

            # Хотя бы 1 общая игра
            candidate_games = set(u.games or [])
            if not user_games_set & candidate_games:
                continue

            candidates.append(u)

        if not candidates:
            return None

        # Выбираем случайного
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