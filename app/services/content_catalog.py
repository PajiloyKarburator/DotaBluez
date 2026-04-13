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
    "prime_month": 60,
    "prime_3m": 160,
    "prime_6m": 300,
    "prime_12m": 580,

    "gold_month": 90,
    "gold_3m": 250,
    "gold_6m": 480,
    "gold_12m": 940,

    "oracle_1d": 15,
    "oracle_3d": 40,
    "oracle_7d": 90,

    "refresh_1": 10,
    "refresh_3": 25,
    "refresh_5": 40,

    "second_chance_1": 50,
    "second_chance_3": 140,
    "second_chance_5": 220,
}

# Машинные значения для БД / JSON
GAMES = {
    "dota2": "Dota 2",
    "lol": "League of Legends",
    "csgo": "CS:GO",
    "valorant": "Valorant",
    "apex": "Apex Legends",
    "hd2": "Helldivers 2",
    "eft": "Escape from Tarkov",
    "dbd": "Dead by Daylight",
    "wot": "World of Tanks",
    "wt": "War Thunder",
    "drg": "Deep Rock Galactic",
    "brawlstars": "Brawl Stars",
    "mobile_legends": "Mobile Legends",
    "pubg": "PUBG",
    "fortnite": "Fortnite",
    "repo": "R.E.P.O.",
    "warframe": "Warframe",
}

GAME_TAGS = {
    "dota2": {
        "dota2_carry": "Керри",
        "dota2_mid": "Мидер",
        "dota2_offlane": "Оффлейн",
        "dota2_half_support": "Поддержка",
        "dota2_support": "Полная Поддержка",
    },
    "lol": {
        "lol_top": "Топ-лейнер",
        "lol_forest": "Лесник",
        "lol_mid": "Мид-лейнер",
        "lol_bot": "Бот-лейнер",
        "lol_support": "Поддержка",

    },
    "csgo": {
        "csgo_rifler": "Rifler",
        "csgo_awper": "AWPer",
        "csgo_igl": "IGL",
    },
    "valorant": {
        "valorant_duelist": "Дуэлист",
        "valorant_controller": "Контроллер",
        "valorant_initiator": "Инициатор",
        "valorant_sentinel": "Страж",
    },
    "apex": {
        "apex_entry": "Разведка",
        "apex_support": "Поддержка",
        "apex_igl": "Штурм",
        "apex_sniper": "Снайпер",
    },
    "hd2": {
        "hd2_heavy": "Штурмовик",
        "hd2_control": "Контроль",
        "hd2_sniper": "Снайпер",
        "hd2_support": "Инженер",
    },
    "eft": {
        "eft_sniper": "Снайпер",
        "eft_mule": "Мул",
        "eft_scout": "Разведчик",
        "eft_hiiler": "Санитар",
    },
    "wot": {
        "wot_tt": "Тяжелый танк",
        "wot_st": "Средний танк",
        "wot_lt": "Легкий танк",
        "wot_pt": "ПТ-САУ",
        "wot_art": "САУ",
    },
    "wt": {
        "wt_tt": "Тяжелый танк",
        "wt_st": "Средний танк",
        "wt_lt": "Легкий танк",
        "wt_pt": "ПТ-САУ",
    },
    "drg": {
        "drg_scout": "Скаут",
        "drg_engineer": "Инженер",
        "drg_driller": "Бурильщик",
        "drg_gunner": "Стрелок",
    },
    "brawlstars": {
        "brawlstars_assasin": "Ассасин",
        "brawlstars_support": "Поддержка",
        "brawlstars_tank": "Танк",
        "brawlstars_marksman": "Стрелок",
        "brawlstars_artilery": "Артилерия",
        "brawlstars_control": "Контроль",
    },
    "dbd": {
        "dbd_survivor": "Выживший",
        "dbd_killer": "Маньяк",
    },
    "mobile_legends": {
        "ml_gold_lane": "Gold Lane",
        "ml_mid_lane": "Mid Lane",
        "ml_exp_lane": "EXP Lane",
        "ml_roam": "Roam",
        "ml_jungle": "Jungle",
    },
    "pubg": {
        "pubg_entry_fragger": "Entry fragger",
        "pubg_scout": "Scout",
        "pubg_sniper": "Sniper",
        "pubg_support": "Support",
        "pubg_igl": "IGL",
    },
    "fortnite": {
        "fortnite_builder": "Builder",
        "fortnite_aimer": "Fragger",
        "fortnite_igl": "IGL",
        "fortnite_support": "Support",
    },
    "repo": {
        "repo_scavenger": "Scavenger",
        "repo_looter": "Looter",
        "repo_tactician": "Tactician",
        "repo_support": "Support",
    },
    "warframe": {
        "warframe_dps": "DPS",
        "warframe_support": "Support",
        "warframe_farm": "Farm",
        "warframe_speedrun": "Speedrun",
    },

}

CONTENT_EMOJI = {
    "prime": "💎",
    "gold": "🥇",
    "oracle": "🔮",
    "second_chance": "♻️",
    "refresh": "⚡",
}