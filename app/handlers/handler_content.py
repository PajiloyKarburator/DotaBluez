from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from app.db.session import SessionLocal
from app.keyboards.keyboard import (
    content_catalog_keyboard,
    content_detail_keyboard,
    content_menu_keyboard,
    content_tariffs_keyboard,
    my_content_keyboard,
)
from app.services.content_catalog import STARS_TARIFF_PRICES as STARS_PRICES
from app.repo.repository import UserRepo
from app.services.content_service import ContentService

router = Router()

user_repo = UserRepo()
content_service = ContentService(user_repo)

CONTENT_DESCRIPTION_TEXTS = {
    "prime": (
        "💎 <b>Prime</b>\n\n"
        "Для тех, кто хочет играть чаще, искать быстрее и получать больше шансов "
        "на хороший матч.\n\n"
        "Что даёт:\n"
        "— больше анкет за один поиск\n"
        "— более быстрое обновление поиска\n"
        "— приоритет в подборе\n"
        "— до 3 анкет для разных игр\n"
        "— 💎 статус в профиле\n\n"
        "Хороший выбор, если ты регулярно играешь и хочешь заметный буст без перегиба."
    ),
    "gold": (
        "🥇 <b>Gold</b>\n\n"
        "Максимальный уровень доступа для тех, кто хочет выжимать из Dota Blues "
        "всё возможное.\n\n"
        "Что даёт:\n"
        "— поиск почти без ожидания\n"
        "— больше анкет за поиск\n"
        "— максимальный приоритет в подборе\n"
        "— неограниченное количество анкет для разных игр\n"
        "— доступ к сбросу рейтинга\n"
        "— 🥇 статус с выделением\n\n"
        "Если нужен лучший опыт и минимум ограничений — это топовый вариант."
    ),
    "oracle": (
        "🔮 <b>Oracle</b>\n\n"
        "Больше информации — меньше случайных каток.\n\n"
        "Что даёт:\n"
        "— просмотр рейтинга других игроков\n"
        "— понимание, кого действительно стоит брать в пати\n"
        "— больше уверенности перед матчем\n\n"
        "Подходит тем, кто хочет выбирать тиммейтов осознанно, а не на удачу."
    ),
    "second_chance": (
        "♻️ <b>Second Chance</b>\n\n"
        "Иногда всем нужен новый старт.\n\n"
        "Что даёт:\n"
        "— сброс рейтинга\n"
        "— шанс восстановить репутацию\n"
        "— возможность начать заново после неудачного периода\n\n"
        "Полезно, если хочешь вернуть профилю нормальный вид и снова спокойно искать пати."
    ),
    "refresh": (
        "⚡ <b>Refresh</b>\n\n"
        "Не хочешь ждать — обновляй поиск сразу.\n\n"
        "Что даёт:\n"
        "— мгновенное обновление выдачи\n"
        "— новые анкеты без ожидания\n"
        "— больше попыток быстро найти подходящего тиммейта\n\n"
        "Идеально, когда хочется ускорить поиск прямо сейчас."
    ),
}


def build_payment_payload(user_id: int, tariff_code: str) -> str:
    return f"content_buy:{user_id}:{tariff_code}"


def parse_payment_payload(payload: str) -> tuple[int, str] | None:
    parts = payload.split(":")
    if len(parts) != 3:
        return None

    action, raw_user_id, tariff_code = parts
    if action != "content_buy":
        return None

    try:
        user_id = int(raw_user_id)
    except ValueError:
        return None

    return user_id, tariff_code


async def show_content_menu(target: Message | CallbackQuery) -> None:
    text = (
        "🎁 <b>Доп Контент Dota Blues</b>\n\n"
        "Здесь ты можешь усилить свой поиск, открыть дополнительные возможности "
        "и сделать подбор тиммейтов удобнее.\n\n"
        "Выбирай:\n"
        "— оформить нужную услугу\n"
        "— или посмотреть, что уже активно у тебя"
    )

    if isinstance(target, Message):
        await target.answer(
            text,
            reply_markup=content_menu_keyboard(),
            parse_mode="HTML",
        )
    else:
        await target.message.edit_text(
            text,
            reply_markup=content_menu_keyboard(),
            parse_mode="HTML",
        )
        await target.answer()


@router.message(F.text == "Доп Контент")
async def content_menu_message(message: Message, state: FSMContext) -> None:
    await state.clear()
    await show_content_menu(message)


@router.callback_query(F.data == "content:menu")
async def content_menu_callback(callback: CallbackQuery) -> None:
    await show_content_menu(callback)


@router.callback_query(F.data == "content:buy")
async def content_buy_callback(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🛒 <b>Магазин Dota Blues</b>\n\n"
        "Здесь собраны улучшения, которые помогают искать быстрее, видеть больше "
        "и получать более сильный опыт от бота.\n\n"
        "Ты можешь выбрать:\n"
        "— подписку для постоянного буста\n"
        "— или отдельную услугу под конкретную задачу\n\n"
        "👇 Нажми на интересующий вариант и посмотри, что он даёт",
        reply_markup=content_catalog_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("content:item:"))
async def content_item_callback(callback: CallbackQuery) -> None:
    content_code = callback.data.split(":")[-1]
    content = content_service.get_content_info(content_code)

    if not content:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    text = CONTENT_DESCRIPTION_TEXTS.get(
        content_code,
        f"✨ <b>{content['title']}</b>\n\nВыбери тариф ниже.",
    )

    await callback.message.edit_text(
        f"{text}\n\n👇 <b>Выбери подходящий тариф:</b>",
        reply_markup=content_tariffs_keyboard(content_code),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("content:tariff:"))
async def content_tariff_callback(callback: CallbackQuery) -> None:
    tariff_code = callback.data.split(":")[-1]

    found = content_service.get_tariff_info(tariff_code)
    if not found:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    price = STARS_PRICES.get(tariff_code)
    if price is None:
        await callback.answer("Для этого тарифа не настроена цена", show_alert=True)
        return

    content_code, content_data, tariff_data = found

    title = tariff_data["title"]
    description = content_data.get("description", "Покупка услуги в Dota Blues")
    payload = build_payment_payload(callback.from_user.id, tariff_code)

    await callback.message.answer_invoice(
        title=title[:32],
        description=description[:255],
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=title[:32], amount=price)],
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery) -> None:
    parsed = parse_payment_payload(pre_checkout_query.invoice_payload)

    if not parsed:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Некорректный платёж.",
        )
        return

    payload_user_id, tariff_code = parsed

    if payload_user_id != pre_checkout_query.from_user.id:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Этот счёт принадлежит другому пользователю.",
        )
        return

    found = content_service.get_tariff_info(tariff_code)
    if not found:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Тариф больше недоступен.",
        )
        return

    expected_amount = STARS_PRICES.get(tariff_code)
    if expected_amount is None:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Цена тарифа не настроена.",
        )
        return

    if pre_checkout_query.currency != "XTR":
        await pre_checkout_query.answer(
            ok=False,
            error_message="Поддерживается только оплата звёздами Telegram.",
        )
        return

    if pre_checkout_query.total_amount != expected_amount:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Сумма платежа устарела. Попробуй ещё раз.",
        )
        return

    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message) -> None:
    payment = message.successful_payment
    parsed = parse_payment_payload(payment.invoice_payload)

    if not parsed:
        await message.answer(
            "Оплата прошла, но не удалось определить товар. Напиши в поддержку."
        )
        return

    payload_user_id, tariff_code = parsed

    if payload_user_id != message.from_user.id:
        await message.answer(
            "Оплата прошла, но пользователь не совпал. Напиши в поддержку."
        )
        return

    with SessionLocal() as db:
        item = content_service.grant_tariff(
            db=db,
            user_id=message.from_user.id,
            tariff_code=tariff_code,
        )

    if not item:
        await message.answer(
            "Оплата прошла, но выдать услугу не удалось. Напиши в поддержку."
        )
        return

    text_lines = [
        "✅ <b>Оплата прошла успешно</b>",
        "",
        f"🎁 <b>{item.get('content_title') or item.get('title', '-')}</b>",
    ]

    if item.get("expires_at"):
        text_lines.append(f"⏳ {content_service.format_remaining(item)}")

    if item.get("remaining_uses") is not None:
        text_lines.append(
            f"📦 Осталось использований: <b>{item['remaining_uses']}</b>"
        )

    text_lines.append("")
    text_lines.append(
        f"🧾 Платёж: <code>{payment.telegram_payment_charge_id}</code>"
    )

    await message.answer(
        "\n".join(text_lines),
        reply_markup=content_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "content:my")
async def my_content_callback(callback: CallbackQuery) -> None:
    with SessionLocal() as db:
        active_items = content_service.get_active_content(db, callback.from_user.id)

    await callback.message.edit_text(
        content_service.build_my_content_text(active_items),
        reply_markup=my_content_keyboard(active_items),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("content:my:item:"))
async def my_content_item_callback(callback: CallbackQuery) -> None:
    content_code = callback.data.split(":")[-1]

    with SessionLocal() as db:
        item = content_service.get_content_detail(
            db,
            callback.from_user.id,
            content_code,
        )

    if not item:
        await callback.answer("Услуга не найдена или уже неактивна", show_alert=True)
        return

    display_title = item.get("content_title") or item.get("title", content_code)

    text_parts = [
        f"🎁 <b>{display_title}</b>",
        "",
        content_service.format_remaining(item),
    ]

    if item.get("expires_at"):
        text_parts.append(f"⏳ Активна до: <code>{item['expires_at']}</code>")

    if item.get("remaining_uses") is not None:
        text_parts.append(
            f"📦 Осталось использований: <b>{item['remaining_uses']}</b>"
        )

    await callback.message.edit_text(
        "\n".join(text_parts),
        reply_markup=content_detail_keyboard(content_code),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("content:use:"))
async def content_use_callback(callback: CallbackQuery) -> None:
    content_code = callback.data.split(":")[-1]

    if content_code == "oracle":
        await callback.answer(
            "Oracle работает по времени и не тратится вручную.",
            show_alert=True,
        )
        return

    if content_code not in {"refresh", "second_chance"}:
        await callback.answer("Эту услугу нельзя использовать вручную.", show_alert=True)
        return

    with SessionLocal() as db:
        item = content_service.consume_usage(
            db,
            callback.from_user.id,
            content_code,
        )

    if not item:
        await callback.answer("Использование недоступно", show_alert=True)
        return

    await callback.message.edit_text(
        "✅ <b>Услуга использована</b>\n\n"
        f"{content_service.format_remaining(item)}",
        reply_markup=content_detail_keyboard(content_code),
        parse_mode="HTML",
    )
    await callback.answer()