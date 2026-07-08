import logging
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice,
)

from services.user_service import STAR_PACKAGES, add_paid_credits

router = Router()
logger = logging.getLogger(__name__)

PAYMENT_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎵 1 песня — 85 ⭐", callback_data="buy_1")],
    [InlineKeyboardButton(text="🎶 5 песен — 365 ⭐", callback_data="buy_5")],
    [InlineKeyboardButton(text="🎁 10 песен — 560 ⭐", callback_data="buy_10")],
])

PAYMENT_MENU_TEXT = (
    "🙏 Спасибо, что пользуешься нашей системой!\n\n"
    "Ваша бесплатная генерация закончилась. Чтобы продолжить получать персональные "
    "песни в подарок — выберите пакет и оплатите звёздами Telegram:"
)

_PACKAGE_TITLES = {
    "buy_1":  "1 песня",
    "buy_5":  "5 песен",
    "buy_10": "10 песен",
}


@router.callback_query(F.data.startswith("buy_"))
async def buy_package(callback: CallbackQuery):
    package_key = callback.data
    package = STAR_PACKAGES.get(package_key)
    if not package:
        await callback.answer("Неизвестный пакет", show_alert=True)
        return

    count, stars = package
    title = _PACKAGE_TITLES.get(package_key, f"{count} песен")

    await callback.answer()
    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"Пакет «{title}»",
        description=f"{count} персональных {'песня' if count == 1 else 'песен'} в подарок",
        payload=package_key,
        currency="XTR",
        prices=[LabeledPrice(label=title, amount=stars)],
        provider_token="",  # для Telegram Stars provider_token не нужен
    )


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    package = STAR_PACKAGES.get(payload)
    user_id = message.from_user.id

    if not package:
        logger.error("Неизвестный payload оплаты: %s", payload)
        await message.answer("Оплата прошла, но пакет не распознан — напишите нам.")
        return

    count, _ = package
    add_paid_credits(user_id, count)
    await message.answer(
        f"✅ Оплата получена! Начислено песен: {count}.\n\n"
        "Отправь /start, чтобы создать песню."
    )
