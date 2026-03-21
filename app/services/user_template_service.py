from __future__ import annotations

from sqlalchemy.orm import Session

from app.repo.repository import UserRepo
from app.db.models import User


class UserTemplateService:
    """Сервис для создания и редактирования пользовательского шаблона."""

    def __init__(self, repo: UserRepo | None = None):
        self.repo = repo or UserRepo()

    def get_profile(self, db: Session, user_id: int) -> User | None:
        return self.repo.get_user_by_id(db, user_id)

    def create_template(
        self,
        db: Session,
        *,
        user_id: int,
        username: str | None,
        age: int,
        img: str | None,
        description: str | None,
        tags: list[str] | None,
        games: list[str] | None,
        rating: int | None,
    ) -> User:
        user = self.repo.get_user_by_id(db, user_id)

        if user:
            return self.repo.update_user(
                db,
                user_id,
                username=username,
                age=age,
                img=img,
                description=description,
                tags=tags,
                games=games,
                rating=rating,
            )

        return self.repo.create_user(
            db,
            id=user_id,
            username=username,
            age=age,
            img=img,
            description=description,
            tags=tags,
            games=games,
            rating=rating,
        )

    def update_template(
        self,
        db: Session,
        *,
        user_id: int,
        username: str | None,
        age: int,
        img: str | None,
        description: str | None,
        tags: list[str] | None,
        games: list[str] | None,
        rating: int | None,
    ) -> User | None:
        return self.repo.update_user(
            db,
            user_id,
            username=username,
            age=age,
            img=img,
            description=description,
            tags=tags,
            games=games,
            rating=rating,
        )

    def update_template_field(
        self,
        db: Session,
        *,
        user_id: int,
        field_name: str,
        value,
    ) -> User | None:
        allowed_fields = {
            "username",
            "age",
            "img",
            "description",
            "tags",
            "games",
            "rating",
        }
        if field_name not in allowed_fields:
            return None

        return self.repo.update_user(db, user_id, **{field_name: value})

    def delete_template(self, db: Session, user_id: int) -> User | None:
        return self.repo.clear_user_profile(db, user_id)

    def profile_is_complete(self, db: Session, user_id: int) -> bool:
        user = self.repo.get_user_by_id(db, user_id)
        if not user:
            return False

        return all(
            [
                user.username not in (None, ""),
                user.age is not None,
                user.description not in (None, ""),
                bool(user.tags),
                bool(user.games),
            ]
        )