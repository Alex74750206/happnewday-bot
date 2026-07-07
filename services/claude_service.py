import re
import anthropic
import asyncio
from config import CLAUDE_API_KEY

_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

SYSTEM_PROMPT = """Ты — профессиональный автор песен с 20-летним опытом.
Ты пишешь персональные песни, которые заставляют людей плакать от счастья.
Твои тексты — это не шаблонные поздравления, а живые истории конкретного человека.
Ты умеешь писать на русском, казахском, английском, французском и немецком языках."""

# Стиль-специфичные инструкции по структуре и подаче
STYLE_GUIDES = {
    "рок": "Рок-стиль: мощные короткие фразы, энергичный ритм, эмоциональный накал. Куплеты — напряжение, припев — взрыв эмоций. Можно восклицания. Избегай нежных образов — ставь сильные глаголы.",
    "rock": "Rock style: short powerful phrases, driving rhythm, emotional intensity. Verses build tension, chorus explodes. Use strong verbs, no gentle imagery.",
    "кантри": "Кантри-стиль: рассказ-история от первого лица, простые образы (дорога, поле, дом, закат), разговорная интонация. Припев — простой и запоминающийся, легко подпевать. Ритм неспешный, певучий.",
    "country": "Country style: first-person storytelling, simple imagery (road, fields, home, sunset), conversational tone. Chorus simple and singable. Slow, melodic rhythm.",
    "поп": "Поп-стиль: яркий крючок в припеве (hook), современный разговорный язык, позитивная энергия. Припев повторяется и легко запоминается. Строки короткие и чёткие.",
    "pop": "Pop style: catchy hook in chorus, modern conversational language, positive energy. Chorus repeatable and memorable. Lines short and punchy.",
    "рэп": "Рэп-стиль: каждый куплет 8-16 строк с внутренними рифмами, быстрый ритм слогов, разговорная подача. Припев — короткий hook (2-4 строки), максимально запоминающийся. Используй образные сравнения.",
    "rap": "Rap style: 8-16 line verses with internal rhymes, fast syllabic rhythm, conversational delivery. Chorus is a short 2-4 line hook, maximally memorable. Use vivid similes.",
    "джаз": "Джаз-стиль: поэтический язык, неожиданные образы, лёгкая меланхолия или игривость. Ритм свободный, строки могут быть неодинаковой длины. Изысканный словарный запас.",
    "jazz": "Jazz style: poetic language, unexpected imagery, light melancholy or playfulness. Free rhythm, lines may vary in length. Sophisticated vocabulary.",
    "инди": "Инди-стиль: интроспективный, метафоричный, искренний. Избегай клише — ищи неожиданные образы для простых чувств. Ритм свободный, атмосфера важнее структуры.",
    "indie": "Indie style: introspective, metaphorical, sincere. Avoid clichés — find unexpected images for simple feelings. Free rhythm, atmosphere over structure.",
    "фолк": "Фолк-стиль: народная нарратив, образы природы и быта, простой искренний язык. Текст как сказание или история.",
    "folk": "Folk style: narrative storytelling, nature and everyday life imagery, simple sincere language. Text like a ballad or tale.",
}

LANG_INSTRUCTIONS = {
    "lang_ru": "Пиши ТОЛЬКО на русском языке.",
    "lang_kz": "Жазу тілі: тек қазақ тілінде жаз. Write ONLY in Kazakh language (қазақша).",
    "lang_en": "Write ONLY in English language.",
    "lang_fr": "Écris UNIQUEMENT en français.",
    "lang_de": "Schreibe NUR auf Deutsch.",
    "lang_kr": "한국어로만 작성하세요. Write ONLY in Korean language (한국어). Use natural Korean lyrical expressions.",
}


def _get_style_guide(style: str) -> str:
    style_lower = style.lower().strip()
    for key, guide in STYLE_GUIDES.items():
        if key in style_lower:
            return guide
    return f"Стиль «{style}»: подбери структуру и лексику, максимально соответствующую этому жанру. Ритм, образы и подача должны сразу считываться как {style}."


QUALITY_EXAMPLE = """ПРИМЕР ПЛАНКИ КАЧЕСТВА (ориентир на уровень конкретики, рифмы и ритма — тему, язык и слова НЕ копируй):
[Куплет]
Ты забываешь ключи у порога опять,
Каждый раз, когда я прихожу домой.
Смеёшься так, что соседи бегут узнавать,
Что случилось — вот это и есть ты такой.

Почему это хорошо: рифма «домой / такой» — точная и стоит на сильной доле; сцена конкретная (ключи у порога), а не абстрактная черта характера; нет инверсий и запрещённых клише."""


# Слова/фразы-клише, которые запрещены промптом, но иногда всё равно проскакивают —
# проверяем программно, чтобы не полагаться только на "честное слово" модели.
BANNED_PHRASES = [
    "ты мой ангел", "добрые глаза", "замечательн", "прекрасн", "особенн",
    "уникальн", "любовь-кровь", "душа-спеша", "сердце-дверца", "мечта-всегда",
]

_TAG_RE = re.compile(r"^\s*\[.*\]\s*$")

# Гласные по языкам — количество гласных букв в строке ≈ количество слогов
# (для русского/казахского это почти точное совпадение, т.к. слоговой центр всегда гласный).
_VOWELS = {
    "lang_ru": "аеёиоуыэюя",
    "lang_kz": "аәеёиоөуұүыэюя",
    "lang_en": "aeiouy",
    "lang_fr": "aeiouyàâéèêëîïôùûü",
    "lang_de": "aeiouyäöü",
}


def _count_syllables(line: str, lang_key: str) -> int:
    if lang_key == "lang_kr":
        # Хангыль — один слоговой блок = один символ Unicode
        return sum(1 for ch in line if "가" <= ch <= "힣")
    vowels = _VOWELS.get(lang_key, _VOWELS["lang_ru"])
    return sum(1 for ch in line.lower() if ch in vowels)


def _find_issues(lyrics: str, lang_key: str, target_syllables: int | None) -> list[str]:
    """Программно проверяет черновик и возвращает список конкретных проблем для точечной правки."""
    issues = []
    lines = [l.strip() for l in lyrics.splitlines() if l.strip() and not _TAG_RE.match(l.strip())]

    if target_syllables:
        for line in lines:
            count = _count_syllables(line, lang_key)
            if abs(count - target_syllables) > 1:
                issues.append(
                    f'Строка "{line}" — примерно {count} слогов вместо целевых ~{target_syllables}, '
                    "перепиши так, чтобы легко пелась в ритме."
                )

    text_lower = lyrics.lower()
    for phrase in BANNED_PHRASES:
        if phrase in text_lower:
            issues.append(f'Найдено запрещённое клише («{phrase}») — замени на конкретный образ из фактов о человеке.')

    return issues[:6]  # не перегружаем правку — достаточно самых явных проблем


async def _check_language_issues(lyrics: str, lang_key: str) -> list[str]:
    """Просит модель найти ДВА типа ошибок, типичных когда слово/фраза подгоняется под рифму/ритм:
    1) несуществующие/искажённые/неуместные слова (напр. «стожок» вместо «стишок»)
    2) грамматические ошибки — падеж, согласование рода/числа, спряжение глагола, синтаксис
       (напр. «спишь на руки мои» вместо «спишь на руках моих» — неверный падеж)."""
    lang_instruction = LANG_INSTRUCTIONS.get(lang_key, LANG_INSTRUCTIONS["lang_ru"])
    response = await asyncio.to_thread(
        _client.messages.create,
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        messages=[{"role": "user", "content":
            f"Вот текст песни:\n\n{lyrics}\n\n"
            f"{lang_instruction}\n\n"
            "Проверь АБСОЛЮТНО КАЖДУЮ строку от начала до самого конца текста — во всех куплетах и "
            "припевах, включая последние строфы, а не только начало. Ищи ДВА типа ошибок:\n\n"
            "1) Несуществующие, искажённые или просто неуместные по смыслу слова — слово похоже на нужное "
            "по звучанию, но на самом деле другое или выдуманное (пример ТИПА ошибки: «стожок» вместо "
            "«стишок» — реальное слово, но не то и не в тему).\n\n"
            "2) ГРАММАТИЧЕСКИЕ ошибки — неверный падеж, неверное согласование рода/числа/падежа между "
            "словами, неверное спряжение или форма глагола, ломаный синтаксис — то есть фраза читается "
            "как НЕПРАВИЛЬНАЯ речь носителя языка, даже если каждое слово по отдельности существует "
            "(пример ТИПА ошибки: «спишь на руки мои» вместо правильного «спишь на руках моих» — неверный "
            "падеж; «она пошёл» вместо «она пошла» — рассогласование рода).\n\n"
            "Ищи ЛЮБЫЕ похожие случаи обоих типов по всему тексту, а не только те, что похожи на примеры.\n\n"
            "Если такие ошибки есть — перечисли ВСЕ найденные случаи построчно, СТРОГО в формате "
            "(без другого текста):\n"
            "СТРОКА: <точная строка целиком, как в тексте> | ПРОБЛЕМА: <что именно не так> | ИСПРАВЬ НА: "
            "<как правильно должна звучать вся строка целиком>\n\n"
            "Если ни одной проблемы нет — ответь ровно одним словом: NONE"
        }],
    )
    text = response.content[0].text.strip()
    if not text or text.upper().startswith("NONE"):
        return []

    issues = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = {}
        for chunk in line.split("|"):
            key, sep, val = chunk.strip().partition(":")
            if sep:
                parts[key.strip().upper()] = val.strip()
        row, problem, fix = parts.get("СТРОКА", ""), parts.get("ПРОБЛЕМА", ""), parts.get("ИСПРАВЬ НА", "")
        if row and problem:
            issues.append(
                f'В строке «{row}» ошибка: {problem}'
                + (f' — исправь на: «{fix}»' if fix else ' — исправь, сохранив смысл')
                + ', подгони рифму/ритм под исправленный вариант.'
            )
    return issues[:6]


async def _auto_revise(lyrics: str, issues: list[str], lang_key: str, target_syllables: int | None) -> str:
    """Точечно исправляет только строки с найденными проблемами, остальное не трогает."""
    lang_instruction = LANG_INSTRUCTIONS.get(lang_key, LANG_INSTRUCTIONS["lang_ru"])
    issues_text = "\n".join(f"- {i}" for i in issues)
    response = await asyncio.to_thread(
        _client.messages.create,
        model="claude-opus-4-8",
        max_tokens=1500,
        messages=[{"role": "user", "content":
            f"Вот черновик текста песни:\n\n{lyrics}\n\n"
            f"ЯЗЫК: {lang_instruction}\n\n"
            "Автоматическая проверка нашла конкретные проблемы:\n"
            f"{issues_text}\n\n"
            "Исправь ТОЛЬКО перечисленные строки/проблемы. Остальной текст, структуру, теги "
            "[Куплет 1], [Припев] и т.д., смысл и детали — не трогай.\n"
            f"Целевой ритм: ~{target_syllables or '(сохрани текущий)'} слогов в строке (±1).\n"
            "Верни ТОЛЬКО полный исправленный текст с тегами, без комментариев."
        }],
    )
    return response.content[0].text.strip()


async def improve_lyrics(lyrics: str, lang_key: str = "lang_ru") -> str:
    lang_instruction = LANG_INSTRUCTIONS.get(lang_key, LANG_INSTRUCTIONS["lang_ru"])
    response = await asyncio.to_thread(
        _client.messages.create,
        model="claude-opus-4-8",
        max_tokens=1500,
        messages=[{"role": "user", "content":
            f"Вот текст песни:\n\n{lyrics}\n\n"
            f"ЯЗЫК: {lang_instruction}\n\n"
            "Улучши этот текст по трём правилам:\n"
            "1. УДАРЕНИЯ — каждая строка должна легко петься, слоги попадать в ритм, ударные слоги совпадать с сильными долями\n"
            "2. РИФМЫ — только точные рифмы, которые одновременно подходят по смыслу; плохую рифму убери совсем\n"
            "3. СОХРАНИ — смысл, имена, конкретные детали; ничего нового не придумывай\n\n"
            "Сохрани структуру с тегами [Куплет 1], [Куплет 2], [Куплет 3], [Куплет 4], [Припев] и т.д.\n"
            "Верни ТОЛЬКО улучшенный текст с тегами, без комментариев."
        }],
    )
    return response.content[0].text.strip()


_GENDER_WORDS = [
    "male vocal", "female vocal", "male voice", "female voice",
    "man's voice", "woman's voice", "masculine vocal", "feminine vocal",
    "men's vocal", "women's vocal", "boy vocal", "girl vocal",
]

def _strip_gender(text: str) -> str:
    """Удаляет гендерные слова из строки тегов чтобы не конфликтовать с выбором пользователя."""
    result = text.lower()
    for w in _GENDER_WORDS:
        result = result.replace(w, "")
    # Чистим лишние запятые и пробелы
    parts = [p.strip() for p in result.split(",") if p.strip()]
    return ", ".join(parts)


async def get_suno_style(style_input: str, vocal_suno: str = "female vocals") -> tuple[str, str, int | None, str]:
    """Возвращает (suno_tags, rhythm_hint, target_syllables, lyrical_style_hint).
    style_input: жанр, артист, или указание конкретной песни в ЛЮБОМ формате написания
    («Артист — Песня», «Артист + Песня», «Артист: Песня», «группа X песня Y», без разделителя и т.д.) —
    определение того, что это именно конкретная песня, делает сама модель, а не regex по разделителям.
    vocal_suno: выбранный пользователем вокал — передаётся чтобы LINE 3 описывал ТЕХНИКУ под этот голос.
    target_syllables: целевое число слогов в строке — используется для программной проверки текста.
    lyrical_style_hint: описание манеры письма (рифмы, образность, лексика) — передаётся в generate_lyrics,
    чтобы текст песни имитировал стиль указанного артиста/трека, а не только музыку."""

    response = await asyncio.to_thread(
        _client.messages.create,
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content":
            f'Input describing the desired musical style: "{style_input}"\n\n'
            "First (silently, do not show this in your answer) decide whether this input references ONE "
            "SPECIFIC EXISTING SONG by a real artist/band, regardless of formatting or punctuation: it may "
            "use a dash/plus/colon/comma between artist and title, words like \"песня\"/\"трек\"/\"song\", or "
            "just \"Artist Title\" with no separator at all. If it clearly names both an artist/band AND a "
            "song title (in any language, any format) — treat it as a SPECIFIC SONG reference and analyze "
            "THAT exact track precisely (real instruments, actual BPM if known, production era, specific "
            "sound of that recording). Otherwise treat it as just a genre/artist style with no particular "
            "track — describe the typical sound and main instruments of that style/artist in general.\n\n"
            "Respond with EXACTLY 4 lines below, each starting with the exact prefix shown, and NOTHING ELSE — "
            "no reasoning, no headers, no markdown, no explanation of your decision, no blank lines between them:\n\n"
            "TAGS: Suno AI music style tags in English, comma-separated, 10-14 tags. Order matters (earlier = "
            "higher weight): 1) BPM (exact if known) or tempo feel, 2) rhythm/beat type (live drums, drum "
            "machine, trap beat...), 3) genre, 4) specific instruments (name them explicitly), 5) production "
            "style/era/mood. NO vocal descriptors here. NEVER mention artist or song names.\n"
            "RHYTHM: a single integer = target syllable count per lyric line, then ' | ', then a short English "
            "phrase about rhythm feel. Example: 8 | moderate tempo, conversational flow. Fast/energetic songs "
            "get fewer syllables (6-8), slow ballads more (9-12).\n"
            f"VOCAL: vocal technique and delivery for a {vocal_suno} singer, matching the identified "
            "song/genre/artist spirit. English, comma-separated, 5-8 descriptors: voice texture (raspy, smooth, "
            "breathy, husky, crystalline, warm...), technique (vibrato, falsetto, belt, growl, whisper...), "
            "phrasing (conversational, staccato, legato, spoken word...), emotional tone. STRICTLY FORBIDDEN: "
            "gender words (male/female/man/woman/boy/girl). NEVER mention artist name.\n"
            "LYRICAL: lyrical WRITING STYLE of that song/artist/genre, in RUSSIAN, 2-3 short sentences, for a "
            "Russian songwriter to imitate the MANNER of writing (not the topic): схема рифмовки (точные простые "
            "AABB / перекрёстные ABAB / свободный стих / внутренние рифмы), образность и лексика (разговорная / "
            "сленг / поэтичная с метафорами / мрачная / ироничная), манера строк (короткие рубленые / длинные "
            "повествовательные / повторы-хуки). НЕ упоминай имя артиста или название песни.\n"
        }],
    )
    raw = response.content[0].text.strip()

    def _extract(label: str) -> str:
        m = re.search(rf'(?im)^\s*{label}\s*:\s*(.+)$', raw)
        return m.group(1).strip() if m else ""

    suno_tags   = _strip_gender(_extract("TAGS")) or style_input
    line2       = _extract("RHYTHM")
    vocal_style = _strip_gender(_extract("VOCAL"))
    lyrical_style_hint = _extract("LYRICAL")

    target_syllables = None
    rhythm_hint = line2
    if "|" in line2:
        num_part, _, rest = line2.partition("|")
        num_part = num_part.strip()
        if num_part.isdigit():
            target_syllables = int(num_part)
        rhythm_hint = rest.strip()

    # Объединяем музыкальные теги и особенности голоса
    if vocal_style:
        suno_tags = f"{suno_tags}, {vocal_style}"
    return suno_tags, rhythm_hint, target_syllables, lyrical_style_hint


async def generate_lyrics(name: str, relationship: str, facts: str, laugh_phrase: str,
                          occasion: str, style: str,
                          lang_key: str = "lang_ru", lang_native: str = "русском",
                          rhythm_hint: str = "", vocal_hint: str = "",
                          target_syllables: int | None = None,
                          lyrical_style_hint: str = "") -> str:

    lang_instruction = LANG_INSTRUCTIONS.get(lang_key, LANG_INSTRUCTIONS["lang_ru"])
    style_guide = _get_style_guide(style)

    prompt = f"""Напиши текст песни в стиле {style}.
Песня — подарок для {name}, это {'мой/моя' if not relationship else f'мой/моя {relationship}'}.

ГЛАВНЫЙ ПРИОРИТЕТ (важнее всех правил ниже): каждая строка должна быть понятна с первого прочтения,
как обычная человеческая речь — грамматически естественная, без вывернутого порядка слов и без
натянутых по смыслу конструкций ради рифмы или ритма. Если рифма, ритм или стиль вступают в
конфликт с ясностью смысла — жертвуй рифмой, ритмом или стилем, но НИКОГДА не жертвуй смыслом.
Плохая рифма или чуть смещённый ритм — это нормально и незаметно на слух. Непонятная или
искажённая фраза — это заметно всегда и портит всю песню.

ЯЗЫК: {lang_instruction}

ДАННЫЕ О ЧЕЛОВЕКЕ:
Имя: {name}
Кем приходится: {relationship}
Три факта из жизни: {facts}
Живые детали (как смеётся / коронная фраза / привычка): {laugh_phrase}
Повод: {occasion}

СТИЛЕВЫЕ ТРЕБОВАНИЯ:
{style_guide}

{f"МАНЕРА ПИСЬМА (пиши в такой же манере — рифмы, образность, лексика — как у {style}, но только про {name} и его историю, без цитат из оригинала): {lyrical_style_hint}" if lyrical_style_hint else ""}

{QUALITY_EXAMPLE}

ВОКАЛ: {vocal_hint if vocal_hint else "женский"}. {"Для детского вокала: простые слова, короткие строки, игривый тон, никакой грусти или сложных образов." if vocal_hint == "Детский" else ""}
НАСТРОЕНИЕ: определяется ТОЛЬКО стилем «{style}» и манерой письма выше — не навязывай одно и то же
тёплое/мягкое/сентиментальное звучание всем стилям одинаково. Если стиль агрессивный, ироничный,
мрачный, дерзкий и т.п. — таким и должно быть настроение песни, без искусственной теплоты.
Читатель должен узнать конкретного человека — это про факты и детали, а не про эмоциональный тон.

СТРУКТУРА — строго соблюдай:
[Куплет 1]
(4 строки — первая встреча с образом человека, конкретная сцена)

[Припев]
(4 строки — эмоциональный пик, с именем {name}, легко запоминается)

[Куплет 2]
(4 строки — другой момент из жизни, живая деталь)

[Припев]
(те же 4 строки)

[Куплет 3]
(4 строки — коронная фраза или характерная привычка человека)

[Припев]
(те же 4 строки)

[Куплет 4]
(4 строки — итоговый, самый личный и эмоциональный)

[Припев]
(те же 4 строки)

ПРАВИЛА КОНКРЕТИКИ (КРИТИЧЕСКИ ВАЖНО):
— Используй детали из фактов буквально: если человек «поливает 12 горшков» — напиши про горшки, не про «любовь к природе»
— Если есть коронная фраза — вплети её в текст как цитату или намёк
— Каждая строфа = одна конкретная сцена, которую можно представить визуально
— ЗАПРЕЩЕНО: «ты мой ангел», «добрые глаза», «замечательный», «прекрасный», «особенный», «уникальный»
— ЗАПРЕЩЕНО: «любовь-кровь», «душа-спеша», «сердце-дверца», «мечта-всегда»

ПРАВИЛА РИФМ:
— {"Схема рифмовки — как указано выше в «МАНЕРА ПИСЬМА»" if lyrical_style_hint else "Схема ABCB (рифмуются 2-я и 4-я строки)"}
— Рифмующееся слово должно подходить по СМЫСЛУ — лучше без рифмы или с неточной рифмой, чем
  бессмысленное, выдуманное или искажённое слово (напомню: смысл важнее рифмы, см. ГЛАВНЫЙ ПРИОРИТЕТ выше)
— Предпочтительны точные рифмы, но НЕ ценой смысла

ПРАВИЛА РИТМА И ЯЗЫКА:
— Ритм исполнителя/жанра: {rhythm_hint if rhythm_hint else f"подбери количество слогов под жанр «{style}»"}
{f"— Целевое количество слогов в каждой строке: примерно {target_syllables} (±1)" if target_syllables else ""}
— Все строки укладываются в этот ритм — слоги совпадают с долями, строку легко петь без «растягивания» слов
— Живой разговорный язык
— ЗАПРЕЩЕНЫ инверсии: «знаю я», «вижу я», «не видать мне»

ФОРМАТ: только текст с тегами [Куплет 1], [Припев], [Куплет 2], [Припев], [Куплет 3], [Припев], [Куплет 4], [Припев]. Без комментариев."""

    response = await asyncio.to_thread(
        _client.messages.create,
        model="claude-opus-4-8",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    draft = response.content[0].text.strip()

    # Автоматическая проверка черновика (слоги + клише + бессмысленные/неверные слова) и точечная
    # правка, если найдены проблемы — пользователь сразу видит уже подправленный вариант,
    # кнопка "Улучшить" остаётся для ручной доводки.
    issues = _find_issues(draft, lang_key, target_syllables)
    try:
        issues += await _check_language_issues(draft, lang_key)
    except Exception:
        pass  # если проверка слов упала — не блокируем генерацию, просто пропускаем этот источник
    if issues:
        try:
            draft = await _auto_revise(draft, issues, lang_key, target_syllables)
        except Exception:
            pass  # если автоправка упала — отдаём исходный черновик, а не роняем генерацию

    return draft
