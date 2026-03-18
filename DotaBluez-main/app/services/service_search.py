from dataclasses import dataclass, field
from app.repo.repository import ProfileRepository


@dataclass
class ProfileCard:
    """Карточка анкеты для отображения пользователю."""
    id: int
    age: int
    img: str
    description: str
    tags: list[str]
    likes: int
    games: list[str]
    games_score: int = 0
    tags_score: int = 0


@dataclass
class RecommendationSession:
    """Сессия просмотра анкет для одного пользователя."""
    user_id: int
    queue: list[ProfileCard] = field(default_factory=list)
    current_index: int = 0

    @property
    def current_card(self) -> ProfileCard | None:
        if 0 <= self.current_index < len(self.queue):
            return self.queue[self.current_index]
        return None

    @property
    def is_empty(self) -> bool:
        return self.current_index >= len(self.queue)

    def advance(self) -> ProfileCard | None:
        """Перейти к следующей карточке."""
        self.current_index += 1
        return self.current_card

    @property
    def remaining(self) -> int:
        return max(0, len(self.queue) - self.current_index)


class SearchService:
    """
    Сервис поиска и рекомендаций анкет.

    Управляет очередью карточек, подгружает новые порции
    из БД, обрабатывает свайпы (лайк/дизлайк).
    """

    BATCH_SIZE = 20
    PREFETCH_THRESHOLD = 3

    def __init__(self, repo: ProfileRepository):
        self.repo = repo
        self._sessions: dict[int, RecommendationSession] = {}

    async def start_session(
        self,
        user_id: int,
        age_min: int = 0,
        age_max: int = 100,
    ) -> ProfileCard | None:
        """
        Начать новую сессию просмотра.
        Возвращает первую карточку или None если кандидатов нет.
        """
        session = RecommendationSession(user_id=user_id)
        self._sessions[user_id] = session

        await self._load_batch(session, age_min, age_max)

        return session.current_card

    async def get_current_card(self, user_id: int) -> ProfileCard | None:
        """Получить текущую карточку пользователя."""
        session = self._sessions.get(user_id)
        if not session:
            return None
        return session.current_card

    async def swipe(
        self,
        user_id: int,
        is_like: bool,
        age_min: int = 0,
        age_max: int = 100,
    ) -> tuple[ProfileCard | None, bool]:
        """
        Обработать свайп текущей карточки.

        Возвращает:
            (следующая_карточка, is_match)
        """
        session = self._sessions.get(user_id)
        if not session or session.is_empty:
            return None, False

        current = session.current_card
        is_match = False

        if current:
            is_match = await self.repo.record_swipe(
                swiper_id=user_id,
                target_id=current.id,
                is_like=is_like,
            )

        next_card = session.advance()

        # Подгружаем новую порцию если карточек мало
        if session.remaining <= self.PREFETCH_THRESHOLD:
            await self._load_batch(session, age_min, age_max)
            if next_card is None:
                next_card = session.current_card

        return next_card, is_match

    async def skip(self, user_id: int) -> ProfileCard | None:
        """Пропустить карточку без записи в БД."""
        session = self._sessions.get(user_id)
        if not session:
            return None
        return session.advance()

    def end_session(self, user_id: int):
        """Завершить сессию просмотра."""
        self._sessions.pop(user_id, None)

    def has_session(self, user_id: int) -> bool:
        """Проверить, есть ли активная сессия."""
        return user_id in self._sessions

    async def _load_batch(
        self,
        session: RecommendationSession,
        age_min: int,
        age_max: int,
    ):
        """Подгрузить порцию кандидатов из БД."""
        user_profile = await self.repo.get_user_profile(session.user_id)

        preferred_games = []
        preferred_tags = []
        if user_profile:
            preferred_games = user_profile.get("games") or []
            preferred_tags = user_profile.get("tags") or []

        swiped_ids = await self.repo.get_swiped_ids(session.user_id)
        queued_ids = [card.id for card in session.queue]
        excluded = list(set(swiped_ids + queued_ids + [session.user_id]))

        candidates = await self.repo.get_candidates(
            user_id=session.user_id,
            excluded_ids=excluded,
            preferred_games=preferred_games,
            preferred_tags=preferred_tags,
            age_min=age_min,
            age_max=age_max,
            limit=self.BATCH_SIZE,
        )

        for row in candidates:
            card = ProfileCard(
                id=row["id"],
                age=row["age"],
                img=row["img"],
                description=row["description"],
                tags=row.get("tags") or [],
                likes=row.get("like", 0),
                games=row.get("games") or [],
                games_score=row.get("games_score", 0),
                tags_score=row.get("tags_score", 0),
            )
            session.queue.append(card)