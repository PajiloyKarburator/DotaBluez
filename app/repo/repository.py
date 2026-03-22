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
    ) -> User:
        user = User(
            id=id,
            username=username.strip() if username else None,
            age=age,
            img=img,
            description=description,
            tags=self._normalize_list(tags),
            games=self._normalize_list(games),
            rating=rating,
            exclusive={},
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def get_user_by_id(self, db: Session, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return db.scalar(stmt)

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
            "age",
            "img",
            "description",
            "tags",
            "games",
            "rating",
            "exclusive",
        }

        for field_name, value in fields.items():
            if field_name not in allowed_fields:
                continue

            if field_name == "tags":
                value = self._normalize_list(value)

            if field_name == "games":
                value = self._normalize_list(value)

            if field_name == "username" and isinstance(value, str):
                value = value.strip()

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