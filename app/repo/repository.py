from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


class UserRepo:
    """Минимальный репозиторий для работы с пользователем и его шаблоном."""

    @staticmethod
    def _normalize_str(value: str) -> str:
        return value.strip().lower()

    @classmethod
    def _normalize_list(cls, values: list[str] | None) -> list[str]:
        if not values:
            return []

        result: list[str] = []
        for value in values:
            if not isinstance(value, str):
                continue

            cleaned = cls._normalize_str(value)
            if cleaned:
                result.append(cleaned)

        return list(dict.fromkeys(result))

    @staticmethod
    def _normalize_int_list(values: list[int] | None) -> list[int]:
        if not values:
            return []
        result: list[int] = []
        for value in values:
            if isinstance(value, int):
                result.append(value)
        return list(dict.fromkeys(result))

    def create_user(
        self,
        db: Session,
        *,
        id: int,
        username: str | None = None,
        age: int,
        img: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        games: list[str] | None = None,
        rating: int | None = None,
        tg_user_id: str | None = None,
        exclusive: dict | None = None,
        teammates: list[int] | None = None,
        is_reported: bool = False,
    ) -> User:
        user = User(
            id=id,
            username=username.strip() if username else None,
            tg_user_id=tg_user_id,
            age=age,
            img=img,
            description=description,
            tags=self._normalize_list(tags),
            games=self._normalize_list(games),
            rating=rating,
            exclusive=exclusive if isinstance(exclusive, dict) else {},
            teammates=self._normalize_int_list(teammates),
            is_reported=is_reported,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def get_user_by_id(self, db: Session, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return db.scalar(stmt)

    def ensure_user_exists(
        self,
        db: Session,
        *,
        user_id: int,
        username: str | None = None,
        tg_user_id: str | None = None,
    ) -> User:
        user = self.get_user_by_id(db, user_id)
        if user:
            changed = False

            clean_username = username.strip() if isinstance(username, str) and username.strip() else None
            clean_tg_user_id = tg_user_id.strip() if isinstance(tg_user_id, str) and tg_user_id.strip() else None

            if clean_username and user.username != clean_username:
                user.username = clean_username
                changed = True

            if clean_tg_user_id and user.tg_user_id != clean_tg_user_id:
                user.tg_user_id = clean_tg_user_id
                changed = True

            if user.exclusive is None:
                user.exclusive = {}
                changed = True

            if user.teammates is None:
                user.teammates = []
                changed = True

            if user.tags is None:
                user.tags = []
                changed = True

            if user.games is None:
                user.games = []
                changed = True

            if changed:
                db.commit()
                db.refresh(user)

            return user

        return self.create_user(
            db,
            id=user_id,
            username=username,
            tg_user_id=tg_user_id,
            age=18,
            img=None,
            description=None,
            tags=[],
            games=[],
            rating=0,
            exclusive={},
            teammates=[],
            is_reported=False,
        )

    def get_all_users(
        self,
        db: Session,
        limit: int = 100,
        offset: int = 0,
    ) -> list[User]:
        stmt = select(User).offset(offset).limit(limit)
        return list(db.scalars(stmt).all())

    def get_users_by_filters(
        self,
        db: Session,
        *,
        tags: list[str] | None = None,
        games: list[str] | None = None,
        min_age: int | None = None,
        max_age: int | None = None,
        min_rating: int | None = None,
        max_rating: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[User]:
        stmt = select(User)

        if min_age is not None:
            stmt = stmt.where(User.age >= min_age)

        if max_age is not None:
            stmt = stmt.where(User.age <= max_age)

        if min_rating is not None:
            stmt = stmt.where(User.rating >= min_rating)

        if max_rating is not None:
            stmt = stmt.where(User.rating <= max_rating)

        normalized_tags = self._normalize_list(tags)
        for tag in normalized_tags:
            stmt = stmt.where(User.tags.contains([tag]))

        normalized_games = self._normalize_list(games)
        for game in normalized_games:
            stmt = stmt.where(User.games.contains([game]))

        stmt = stmt.offset(offset).limit(limit)
        return list(db.scalars(stmt).all())

    def update_user(
        self,
        db: Session,
        user_id: int,
        **fields: Any,
    ) -> User | None:
        user = self.get_user_by_id(db, user_id)
        if not user:
            return None

        allowed_fields = {
            "username",
            "tg_user_id",
            "age",
            "img",
            "description",
            "tags",
            "games",
            "rating",
            "exclusive",
            "teammates",
            "is_reported",
        }

        for field_name, value in fields.items():
            if field_name not in allowed_fields:
                continue

            if field_name == "tags":
                value = self._normalize_list(value)

            if field_name == "games":
                value = self._normalize_list(value)

            if field_name in {"username", "tg_user_id"} and isinstance(value, str):
                value = value.strip()

            if field_name == "teammates":
                value = self._normalize_int_list(value)

            setattr(user, field_name, value)

        db.commit()
        db.refresh(user)
        return user

    def get_user_exclusive(self, db: Session, user_id: int) -> dict:
        user = self.get_user_by_id(db, user_id)
        if not user:
            return {}
        return user.exclusive or {}

    def save_user_exclusive(
        self,
        db: Session,
        user_id: int,
        exclusive: dict,
    ) -> User | None:
        user = self.get_user_by_id(db, user_id)
        if not user:
            return None

        user.exclusive = exclusive
        db.commit()
        db.refresh(user)
        return user

    def clear_user_profile(self, db: Session, user_id: int) -> User | None:
        user = self.get_user_by_id(db, user_id)
        if not user:
            return None

        user.username = None
        user.age = 18
        user.img = None
        user.description = None
        user.tags = []
        user.games = []
        user.rating = None
        user.teammates = []
        user.is_reported = False

        db.commit()
        db.refresh(user)
        return user

    def delete_user(self, db: Session, user_id: int) -> bool:
        user = self.get_user_by_id(db, user_id)
        if not user:
            return False

        db.delete(user)
        db.commit()
        return True

    def add_teammate(self, db: Session, user_id: int, teammate_id: int) -> User | None:
        if user_id == teammate_id:
            return None
        user = self.get_user_by_id(db, user_id)
        if not user:
            return None

        teammates = self._normalize_int_list(user.teammates or [])
        if teammate_id not in teammates:
            teammates.append(teammate_id)
            user.teammates = teammates
            db.commit()
            db.refresh(user)
        return user

    def remove_teammate(self, db: Session, user_id: int, teammate_id: int) -> User | None:
        user = self.get_user_by_id(db, user_id)
        if not user:
            return None

        teammates = self._normalize_int_list(user.teammates or [])
        if teammate_id in teammates:
            teammates.remove(teammate_id)
            user.teammates = teammates
            db.commit()
            db.refresh(user)
        return user

    def get_teammates(self, db: Session, user_id: int) -> list[User]:
        user = self.get_user_by_id(db, user_id)
        if not user:
            return []
        teammate_ids = self._normalize_int_list(user.teammates or [])
        if not teammate_ids:
            return []
        stmt = select(User).where(User.id.in_(teammate_ids))
        users = list(db.scalars(stmt).all())
        users.sort(key=lambda item: teammate_ids.index(item.id))
        return users

    def mark_user_reported(self, db: Session, user_id: int) -> User | None:
        user = self.get_user_by_id(db, user_id)
        if not user:
            return None
        if not user.is_reported:
            user.is_reported = True
            db.commit()
            db.refresh(user)
        return user