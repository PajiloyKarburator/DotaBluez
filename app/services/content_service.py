from datetime import datetime

from app.services.content_catalog import CONTENT_CATALOG


class ContentService:
    def __init__(self, user_repo):
        self.user_repo = user_repo

    def get_content_list(self) -> list[tuple[str, dict]]:
        return list(CONTENT_CATALOG.items())

    def get_content_info(self, content_code: str) -> dict | None:
        return CONTENT_CATALOG.get(content_code)

    def get_tariffs(self, content_code: str) -> dict:
        content = CONTENT_CATALOG.get(content_code)
        if not content:
            return {}
        return content.get("tariffs", {})

    def get_tariff_info(self, tariff_code: str) -> tuple[str, dict, dict] | None:
        for content_code, content_data in CONTENT_CATALOG.items():
            tariffs = content_data.get("tariffs", {})
            if tariff_code in tariffs:
                return content_code, content_data, tariffs[tariff_code]
        return None

    def grant_tariff(self, db, user_id: int, tariff_code: str) -> dict | None:
        found = self.get_tariff_info(tariff_code)
        if not found:
            return None

        content_code, content_data, tariff_data = found
        exclusive = self.user_repo.get_user_exclusive(db, user_id)
        now = datetime.utcnow()

        old_item = exclusive.get(content_code, {}) if isinstance(exclusive.get(content_code), dict) else {}

        item = {
            "content_code": content_code,
            "content_title": content_data["title"],
            "tariff_code": tariff_code,
            "title": tariff_data["title"],
        }

        # Если покупают Gold, а Prime уже есть — Prime пропадает
        if content_code == "gold":
            exclusive.pop("prime", None)

        # Подписки по времени: суммируем срок
        if tariff_data["duration"] is not None:
            current_expires_at = old_item.get("expires_at")
            base_dt = now

            if current_expires_at:
                try:
                    old_dt = datetime.fromisoformat(current_expires_at)
                    if old_dt > now:
                        base_dt = old_dt
                except ValueError:
                    pass

            item["expires_at"] = (base_dt + tariff_data["duration"]).isoformat()
            item.pop("remaining_uses", None)

        # Услуги по использованию: суммируем использования
        if tariff_data["uses"] is not None:
            old_uses = old_item.get("remaining_uses", 0) if isinstance(old_item, dict) else 0
            item["remaining_uses"] = (old_uses or 0) + tariff_data["uses"]
            item.pop("expires_at", None)

        exclusive[content_code] = item
        self.user_repo.save_user_exclusive(db, user_id, exclusive)
        return item

    def get_active_content(self, db, user_id: int) -> dict:
        exclusive = self.user_repo.get_user_exclusive(db, user_id)
        now = datetime.utcnow()

        result = {}
        for content_code, item in exclusive.items():
            if not isinstance(item, dict):
                continue

            expires_at = item.get("expires_at")
            remaining_uses = item.get("remaining_uses")

            if expires_at:
                try:
                    dt = datetime.fromisoformat(expires_at)
                    if dt > now:
                        result[content_code] = item
                except ValueError:
                    continue
            elif isinstance(remaining_uses, int) and remaining_uses > 0:
                result[content_code] = item

        return result

    def get_content_detail(self, db, user_id: int, content_code: str) -> dict | None:
        active = self.get_active_content(db, user_id)
        return active.get(content_code)

    def consume_usage(self, db, user_id: int, content_code: str) -> dict | None:
        exclusive = self.user_repo.get_user_exclusive(db, user_id)
        item = exclusive.get(content_code)

        if not item:
            return None

        remaining_uses = item.get("remaining_uses")
        if not isinstance(remaining_uses, int) or remaining_uses <= 0:
            return None

        item["remaining_uses"] -= 1
        exclusive[content_code] = item
        self.user_repo.save_user_exclusive(db, user_id, exclusive)
        return item

    @staticmethod
    def format_remaining(item: dict) -> str:
        expires_at = item.get("expires_at")
        if expires_at:
            try:
                dt = datetime.fromisoformat(expires_at)
            except ValueError:
                return "Некорректная дата"

            delta = dt - datetime.utcnow()
            total_seconds = int(delta.total_seconds())

            if total_seconds <= 0:
                return "Истекло"

            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60

            parts = []
            if days > 0:
                parts.append(f"{days} д.")
            if hours > 0:
                parts.append(f"{hours} ч.")
            if minutes > 0:
                parts.append(f"{minutes} мин.")

            return "Осталось: " + " ".join(parts)

        remaining_uses = item.get("remaining_uses")
        if isinstance(remaining_uses, int):
            return f"Осталось использований: {remaining_uses}"

        return "Неизвестно"

    def build_my_content_text(self, active_items: dict) -> str:
        if not active_items:
            return (
                "У тебя пока нет активных услуг.\n\n"
                "Зайди в «Приобрести услуги», чтобы посмотреть доступные варианты."
            )

        lines = ["🎁 Твои активные услуги:\n"]
        for content_code, item in active_items.items():
            title = item.get("content_title") or item.get("title") or content_code
            lines.append(f"• {title}")

        return "\n".join(lines)
    

    def has_active_content(self, db, user_id: int, content_code: str) -> bool:
        active = self.get_active_content(db, user_id)
        return content_code in active

    def get_subscription_status(self, db, user_id: int) -> str:
        return self.get_active_subscription(db, user_id)

    def get_subscription_badge(self, db, user_id: int) -> str:
        status = self.get_active_subscription(db, user_id)

        if status == "gold":
            return "🥇 Gold"
        if status == "prime":
            return "💎 Premium"
        return "🆓 Free"

    def get_games_limit(self, db, user_id: int) -> int | None:
        status = self.get_active_subscription(db, user_id)

        if status == "gold":
            return None
        if status == "prime":
            return 3
        return 1
    def get_active_subscription(self, db, user_id: int) -> str:
        exclusive = self.user_repo.get_user_exclusive(db, user_id)
        now = datetime.utcnow()

        gold_item = exclusive.get("gold")
        if isinstance(gold_item, dict):
            expires_at = gold_item.get("expires_at")
            if expires_at:
                try:
                    if datetime.fromisoformat(expires_at) > now:
                        return "gold"
                except ValueError:
                    pass

        prime_item = exclusive.get("prime")
        if isinstance(prime_item, dict):
            expires_at = prime_item.get("expires_at")
            if expires_at:
                try:
                    if datetime.fromisoformat(expires_at) > now:
                        return "prime"
                except ValueError:
                    pass

        return "free"
