from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states import SongStates
from services.user_service import (
    trial_available, songs_left, TRIAL_LIMIT,
    has_generation_available, paid_credits_left,
)
from handlers.payment import PAYMENT_KEYBOARD, PAYMENT_MENU_TEXT

router = Router()

LANGUAGE_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="lang_kz"),
    ],
    [
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
        InlineKeyboardButton(text="🇫🇷 Français", callback_data="lang_fr"),
    ],
    [
        InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="lang_de"),
        InlineKeyboardButton(text="🇰🇷 한국어", callback_data="lang_kr"),
    ],
])


async def send_start_menu(message: Message, state: FSMContext, show_greeting: bool = True):
    """Показывает стартовое меню: язык для новой песни, либо меню оплаты если генераций не осталось.
    Переиспользуется и в /start (show_greeting=True — полное приветствие), и сразу после доставки
    готовой песни (show_greeting=False — короткое приглашение без повторного приветствия)."""
    user_id = message.from_user.id

    if not has_generation_available(user_id):
        await message.answer(PAYMENT_MENU_TEXT, reply_markup=PAYMENT_KEYBOARD)
        return

    left = songs_left(user_id)
    paid = paid_credits_left(user_id)
    if left >= TRIAL_LIMIT:
        status_line = "первая генерация — совершенно бесплатно, а дальше — символическая плата, необходимая для поддержки системы."
    elif paid > 0:
        status_line = f"осталось оплаченных генераций: {paid}."
    else:
        status_line = f"осталось бесплатных генераций: {left}."

    await state.set_state(SongStates.waiting_for_language)

    if show_greeting:
        text = (
            "👋 Привет! Я — самоподдерживающаяся система поздравлений для кого угодно: "
            "для Димы, для Антонины Ивановны, для дорогого начальника — вообще для любого "
            "человека в твоей жизни.\n\n"
            "Я создаю персональные песни в подарок и существую благодаря поддержке пользователей: "
            f"{status_line}\n\n"
            "Выбери язык песни:"
        )
    else:
        text = f"🎵 Готов сделать ещё одну песню! {status_line}\n\nВыбери язык песни:"

    await message.answer(text, reply_markup=LANGUAGE_KEYBOARD)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await send_start_menu(message, state, show_greeting=True)
