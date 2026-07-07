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
            "🎵 Бесплатный лимит песен исчерпан!\n\n"
            f"Бесплатный режим позволяет создать до {TRIAL_LIMIT} персональных песен.\n"
            "Ты уже использовал все бесплатные песни 🎶\n\n"
            "Чтобы создать новую песню — свяжись с нами."
        )
        return

    left = songs_left(user_id)
    await state.set_state(SongStates.waiting_for_language)
    await message.answer(
        "🎵 Привет! Я создам персональную песню в подарок.\n\n"
        f"Осталось бесплатных песен: {left}\n\n"
        "Выбери язык песни:",
        reply_markup=LANGUAGE_KEYBOARD,
    )
