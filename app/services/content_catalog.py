from datetime import timedelta

CONTENT_CATALOG = {
    "prime": {
        "title": "Prime",
        "description": "Подписка Prime на выбранный срок.",
        "tariffs": {
            "prime_month": {
                "title": "Prime — 1 месяц",
                "duration": timedelta(days=30),
                "uses": None,
            },
            "prime_3m": {
                "title": "Prime — 3 месяца",
                "duration": timedelta(days=90),
                "uses": None,
            },
            "prime_6m": {
                "title": "Prime — 6 месяцев",
                "duration": timedelta(days=180),
                "uses": None,
            },
            "prime_12m": {
                "title": "Prime — 1 год",
                "duration": timedelta(days=365),
                "uses": None,
            },
        },
    },
    "gold": {
        "title": "Gold",
        "description": "Подписка Gold на выбранный срок.",
        "tariffs": {
            "gold_month": {
                "title": "Gold — 1 месяц",
                "duration": timedelta(days=30),
                "uses": None,
            },
            "gold_3m": {
                "title": "Gold — 3 месяца",
                "duration": timedelta(days=90),
                "uses": None,
            },
            "gold_6m": {
                "title": "Gold — 6 месяцев",
                "duration": timedelta(days=180),
                "uses": None,
            },
            "gold_12m": {
                "title": "Gold — 1 год",
                "duration": timedelta(days=365),
                "uses": None,
            },
        },
    },
    "oracle": {
        "title": "Oracle",
        "description": "Всевидящее око на выбранный срок.",
        "tariffs": {
            "oracle_1d": {
                "title": "Oracle — 1 день",
                "duration": timedelta(days=1),
                "uses": None,
            },
            "oracle_3d": {
                "title": "Oracle — 3 дня",
                "duration": timedelta(days=3),
                "uses": None,
            },
            "oracle_7d": {
                "title": "Oracle — 7 дней",
                "duration": timedelta(days=7),
                "uses": None,
            },
        },
    },
    "second_chance": {
        "title": "Second Chance",
        "description": "Сброс рейтинга по количеству использований.",
        "tariffs": {
            "second_chance_1": {
                "title": "Second Chance — 1 использование",
                "duration": None,
                "uses": 1,
            },
            "second_chance_3": {
                "title": "Second Chance — 3 использования",
                "duration": None,
                "uses": 3,
            },
            "second_chance_5": {
                "title": "Second Chance — 5 использований",
                "duration": None,
                "uses": 5,
            },
        },
    },
    "refresh": {
        "title": "Refresh",
        "description": "Мгновенное обновление поиска по количеству использований.",
        "tariffs": {
            "refresh_1": {
                "title": "Refresh — 1 использование",
                "duration": None,
                "uses": 1,
            },
            "refresh_3": {
                "title": "Refresh — 3 использования",
                "duration": None,
                "uses": 3,
            },
            "refresh_5": {
                "title": "Refresh — 5 использований",
                "duration": None,
                "uses": 5,
            },
        },
    },
}
STARS_TARIFF_PRICES = {
    "prime_month": 1,
    "prime_3m": 499,
    "prime_6m": 899,
    "prime_12m": 1499,

    "gold_month": 1,
    "gold_3m": 949,
    "gold_6m": 1799,
    "gold_12m": 3299,

    "oracle_1d": 1,
    "oracle_3d": 39,
    "oracle_7d": 69,

    "refresh_1": 1,
    "refresh_3": 59,
    "refresh_5": 89,

    "second_chance_1": 1,
    "second_chance_3": 379,
    "second_chance_5": 549,
}