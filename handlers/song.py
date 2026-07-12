import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext

from config import ADMIN_ID
from states import SongStates
from services.claude_service import generate_lyrics, get_suno_style, improve_lyrics
from services.suno_service import generate_song
from services.user_service import consume_generation, has_generation_available
from services.log_service import log_song, get_log_file_path
from handlers.start import send_start_menu
from handlers.payment import PAYMENT_KEYBOARD, PAYMENT_MENU_TEXT

router = Router()
logger = logging.getLogger(__name__)

# { user_id: {"lyrics": ..., "style": ..., "suno_style": ..., "title": ..., "name": ..., "lang_key": ...} }
_pending: dict = {}

LYRICS_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎵 Создать музыку", callback_data="start_music")],
    [InlineKeyboardButton(text="✏️ Редактировать текст", callback_data="edit_lyrics")],
    [InlineKeyboardButton(text="🤖 Улучшить ударения и рифмы", callback_data="ai_fix_lyrics")],
])

RETRY_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔄 Повторить генерацию музыки", callback_data="start_music")],
    [InlineKeyboardButton(text="✏️ Редактировать текст", callback_data="edit_lyrics")],
])

LANGUAGES = {
    "lang_ru": ("Русский", "русском"),
    "lang_kz": ("Қазақша", "қазақ тілінде"),
    "lang_en": ("English", "English"),
    "lang_fr": ("Français", "français"),
    "lang_de": ("Deutsch", "Deutsch"),
    "lang_kr": ("한국어", "한국어로"),
}

STYLE_EXAMPLES = (
    "• Жанр: поп, рок, джаз, рэп, кантри, инди, фолк...\n"
    "• Артист/группа: «Кино», «Beatles», «Анна Асти»\n"
    "• Артист + песня-образец: «Сектор Газа — Нажми на кнопку»\n\n"
    "Если укажешь конкретную песню — музыка будет максимально похожа именно на неё."
)

VOCAL_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🎤 Мужской", callback_data="vocal_male"),
        InlineKeyboardButton(text="🎤 Женский", callback_data="vocal_female"),
    ],
    [
        InlineKeyboardButton(text="👶 Детский", callback_data="vocal_child"),
    ],
])

VOCALS = {
    "vocal_male":   ("Мужской",  "male vocals, deep male voice"),
    "vocal_female": ("Женский",  "female vocals, female voice"),
    "vocal_child":  ("Детский",  "children's vocals, kids voice, child singer"),
}


@router.callback_query(F.data.startswith("lang_"), SongStates.waiting_for_language)
async def got_language(callback: CallbackQuery, state: FSMContext):
    lang_key = callback.data
    lang_label, lang_native = LANGUAGES.get(lang_key, ("Русский", "русском"))
    await state.update_data(language=lang_key, lang_label=lang_label, lang_native=lang_native)
    await state.set_state(SongStates.waiting_for_vocal)
    await callback.message.edit_text(
        f"✅ Язык: {lang_label}\n\n"
        "Выбери тип вокала для песни:"
        , reply_markup=VOCAL_KEYBOARD
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vocal_"), SongStates.waiting_for_vocal)
async def got_vocal(callback: CallbackQuery, state: FSMContext):
    vocal_key = callback.data
    vocal_label, vocal_suno = VOCALS.get(vocal_key, ("Женский", "female vocals"))
    await state.update_data(vocal_label=vocal_label, vocal_suno=vocal_suno)
    await state.set_state(SongStates.waiting_for_name)
    await callback.message.edit_text(
        f"✅ Вокал: {vocal_label}\n\n"
        "Как зовут человека, которому делаем песню?"
    )
    await callback.answer()


@router.message(F.text, SongStates.waiting_for_name)
async def got_name(message: Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(SongStates.waiting_for_relationship)
    await message.answer(
        f"Кем тебе приходится {name}?\n\n"
        "Например: мама, папа, лучшая подруга, муж, дочь, коллега, друг детства..."
    )


@router.message(F.text, SongStates.waiting_for_relationship)
async def got_relationship(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data["name"]
    await state.update_data(relationship=message.text.strip())
    await state.set_state(SongStates.waiting_for_facts)
    await message.answer(
        f"Теперь три факта из жизни {name} — конкретных, живых:\n\n"
        "Не «любит природу», а «каждое утро поливает 12 горшков на подоконнике»\n"
        "Не «добрая», а «всегда оставляет последний кусок торта другим»\n\n"
        "Напиши три таких момента — по одному на строку или через запятую."
    )


@router.message(F.text, SongStates.waiting_for_facts)
async def got_facts(message: Message, state: FSMContext):
    await state.update_data(facts=message.text.strip())
    await state.set_state(SongStates.waiting_for_laugh_phrase)
    await message.answer(
        "Два живых штриха, которые ни с кем не перепутаешь:\n\n"
        "1. Как он/она смеётся? (громко, заразительно, беззвучно, хрюкает...)\n"
        "2. Фраза, которую он/она часто говорит и которая тебе запомнилась\n\n"
        "Именно эти детали делают песню про конкретного человека, а не «про всех»."
    )


@router.message(F.text, SongStates.waiting_for_laugh_phrase)
async def got_laugh_phrase(message: Message, state: FSMContext):
    await state.update_data(laugh_phrase=message.text.strip())
    await state.set_state(SongStates.waiting_for_occasion)
    await message.answer(
        "По какому поводу песня?\n\n"
        "Например: день рождения, юбилей, свадьба, выпускной, просто так 💛"
    )


@router.message(F.text, SongStates.waiting_for_occasion)
async def got_occasion(message: Message, state: FSMContext):
    await state.update_data(occasion=message.text.strip())
    await state.set_state(SongStates.waiting_for_style)
    await message.answer(
        f"В каком стиле создаём музыку?\n\n{STYLE_EXAMPLES}"
    )


@router.message(F.text, SongStates.waiting_for_style)
async def got_style(message: Message, state: FSMContext):
    data = await state.get_data()
    style = message.text.strip()
    name = data["name"]
    relationship = data.get("relationship", "")
    facts = data["facts"]
    laugh_phrase = data.get("laugh_phrase", "")
    occasion = data["occasion"]
    lang_key = data.get("language", "lang_ru")
    lang_label = data.get("lang_label", "Русский")
    lang_native = data.get("lang_native", "русском")
    vocal_label = data.get("vocal_label", "Женский")
    vocal_suno = data.get("vocal_suno", "female vocals")

    await state.clear()

    status_msg = await message.answer(
        f"✍️ Анализирую стиль и пишу текст... (~30-40 сек)"
    )

    # Определяем ритм и теги Suno до генерации текста — чтобы слоги совпали с темпом
    # vocal_suno передаём чтобы Haiku адаптировал описание голоса под выбранный тип
    suno_tags, rhythm_hint, target_syllables, lyrical_style_hint = await get_suno_style(style, vocal_suno)
    # Вокал пользователя ПЕРВЫМ — наибольший вес в Suno, гарантирует правильный пол
    suno_tags = f"{vocal_suno}, {suno_tags}"

    try:
        lyrics = await generate_lyrics(
            name, relationship, facts, laugh_phrase, occasion, style,
            lang_key, lang_native, rhythm_hint, vocal_label, target_syllables, lyrical_style_hint
        )
    except Exception as e:
        logger.error("Ошибка генерации текста: %s", e)
        await status_msg.edit_text("❌ Не удалось создать текст. Попробуй ещё раз — /start")
        return

    title = f"Песня для {name} — {occasion}"
    user_id = message.from_user.id
    _pending[user_id] = {
        "lyrics": lyrics, "style": style, "suno_style": suno_tags, "title": title,
        "name": name, "occasion": occasion, "lang_key": lang_key,
    }

    await status_msg.edit_text(f"📝 Текст готов!\n\n{lyrics}")
    await message.answer(
        f"🎛 Настройки музыки для Suno:\n{suno_tags}",
        reply_markup=LYRICS_KEYBOARD,
    )


@router.callback_query(F.data == "start_music")
async def start_music(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id
    data = _pending.get(user_id)
    if not data:
        await callback.answer("Данные устарели, начни заново — /start", show_alert=True)
        return

    # Критическая проверка: без неё пользователь мог сгенерировать песню повторным нажатием
    # этой же кнопки, даже если бесплатная генерация уже использована и оплата не прошла.
    if not has_generation_available(user_id):
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(PAYMENT_MENU_TEXT, reply_markup=PAYMENT_KEYBOARD)
        return

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    status_msg = await callback.message.answer("🎵 Создаю музыку... (1-3 мин)")

    if not data.get("suno_style"):
        vocal_suno_saved = data.get("vocal_suno", "female vocals")
        base_tags, _, _, _ = await get_suno_style(data["style"], vocal_suno_saved)
        data["suno_style"] = f"{vocal_suno_saved}, {base_tags}"

    try:
        audio_url = await generate_song(data["lyrics"], data["suno_style"], data["title"])
    except Exception as e:
        logger.error("Ошибка генерации музыки: %s", e)
        err_str = str(e)
        if "SENSITIVE_WORD_ERROR" in err_str:
            hint = "Suno заблокировал текст по фильтру. Попробуй отредактировать текст или повторить."
        else:
            hint = "Что-то пошло не так. Попробуй повторить."
        await status_msg.edit_text(f"❌ Не удалось создать музыку.\n{hint}", reply_markup=RETRY_KEYBOARD)
        return

    consume_generation(user_id)
    try:
        log_song(
            user_id=user_id,
            username=callback.from_user.username or callback.from_user.full_name,
            name=data["name"],
            occasion=data.get("occasion", ""),
            style=data["style"],
            audio_url=audio_url,
            lyrics=data.get("lyrics", ""),
        )
    except Exception as e:
        # Песня уже оплачена и сгенерирована — сбой записи в лог не должен блокировать доставку
        logger.error("Ошибка записи в лог заказов: %s", e)

    # Бот работает в облаке — файл лога нигде на сервере не хранится постоянно,
    # поэтому актуальный excel сразу уходит приватным сообщением только админу.
    try:
        await bot.send_document(
            chat_id=ADMIN_ID,
            document=FSInputFile(get_log_file_path()),
            caption=f"📊 Новый заказ: {data['name']} ({data.get('occasion', '')})",
        )
    except Exception as e:
        logger.error("Ошибка отправки лога админу: %s", e)

    _pending.pop(user_id, None)
    await status_msg.delete()
    await _send_audio(
        callback.message, audio_url, data["title"],
        data["name"], data.get("occasion", ""), data["style"]
    )
    await send_start_menu(callback.message, state, show_greeting=False)


@router.callback_query(F.data == "edit_lyrics")
async def edit_lyrics_cb(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not _pending.get(user_id):
        await callback.answer("Данные устарели, начни заново — /start", show_alert=True)
        return
    await callback.answer()
    await state.set_state(SongStates.waiting_for_edited_lyrics)
    await callback.message.answer(
        "✏️ Скопируй текст выше, отредактируй и пришли мне исправленный вариант.\n\n"
        "Сохраняй теги [Куплет 1], [Припев] и т.д. — они важны для структуры музыки."
    )


@router.message(F.text, SongStates.waiting_for_edited_lyrics)
async def got_edited_lyrics(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = _pending.get(user_id)
    if not data:
        await state.clear()
        await message.answer("Данные устарели, начни заново — /start")
        return

    data["lyrics"] = message.text.strip()
    data.pop("suno_style", None)
    await state.clear()

    await message.answer(
        f"✅ Текст обновлён!\n\n{data['lyrics']}",
        reply_markup=LYRICS_KEYBOARD,
    )


@router.callback_query(F.data == "ai_fix_lyrics")
async def ai_fix_lyrics_cb(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = _pending.get(user_id)
    if not data:
        await callback.answer("Данные устарели, начни заново — /start", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    status_msg = await callback.message.answer("🤖 Исправляю ударения и рифмы... (~20 сек)")

    try:
        improved = await improve_lyrics(data["lyrics"], data.get("lang_key", "lang_ru"))
        data["lyrics"] = improved
        data.pop("suno_style", None)
    except Exception as e:
        logger.error("Ошибка улучшения текста: %s", e)
        await status_msg.edit_text("❌ Не удалось улучшить текст.", reply_markup=LYRICS_KEYBOARD)
        return

    await status_msg.edit_text(
        f"✅ Текст улучшен!\n\n{improved}",
        reply_markup=LYRICS_KEYBOARD,
    )


async def _send_audio(message: Message, audio_url: str, title: str,
                      name: str, occasion: str, style: str):
    try:
        await message.answer_audio(
            audio=audio_url,
            title=title,
            caption=f"🎵 Персональная песня для {name}!\nПовод: {occasion} · Стиль: {style}",
        )
    except Exception:
        await message.answer(f"🎵 Песня готова!\n\nСлушай: {audio_url}")
