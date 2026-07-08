from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states import SongStates
from services.user_service import trial_available, songs_left, TRIAL_LIMIT

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


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if not trial_available(user_id):
        await message.answer(
            "🎵 Твоя бесплатная песня уже создана!\n\n"
            "Я живу благодаря поддержке пользователей, поэтому дальше — символическая плата "
            "за каждую новую песню, которая помогает системе оставаться на плаву 🎶\n\n"
            "Чтобы создать ещё одну песню — свяжись с нами."
        )
        return

    left = songs_left(user_id)
    await state.set_state(SongStates.waiting_for_language)
    await message.answer(
        "👋 Привет! Я — самоподдерживающаяся система поздравлений для кого угодно: "
        "для Димы, для Антонины Ивановны, для дорогого начальника — вообще для любого "
        "человека в твоей жизни.\n\n"
        "Я создаю персональные песни в подарок и существую благодаря поддержке пользователей: "
        f"{'первая генерация' if left >= TRIAL_LIMIT else f'осталось бесплатных генераций: {left}'} "
        "— совершенно бесплатно, а дальше — символическая плата, необходимая для поддержки системы.\n\n"
        "Выбери язык песни:",
        reply_markup=LANGUAGE_KEYBOARD,
    )
