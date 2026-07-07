import re
import aiohttp
import asyncio
from config import KIE_API_KEY

KIE_BASE_URL = "https://api.kie.ai"
POLL_INTERVAL = 10
MAX_WAIT = 300

FINAL_STATUSES = {"SUCCESS", "CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED",
                  "CALLBACK_EXCEPTION", "SENSITIVE_WORD_ERROR"}
ERROR_STATUSES = {"CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED",
                  "CALLBACK_EXCEPTION", "SENSITIVE_WORD_ERROR"}

# Suno понимает только английские структурные теги
_TAG_MAP = {
    "куплет 1": "Verse 1",
    "куплет 2": "Verse 2",
    "куплет 3": "Verse 3",
    "куплет 4": "Verse 4",
    "куплет 5": "Verse 5",
    "припев":   "Chorus",
    "мост":     "Bridge",
    "outro":    "Outro",
    "вступление": "Intro",
    "интро":    "Intro",
}

# Русские названия жанров → английские теги для Suno
_STYLE_MAP = {
    "поп":           "pop",
    "рок":           "rock",
    "рэп":           "rap",
    "джаз":          "jazz",
    "кантри":        "country",
    "инди":          "indie",
    "фолк":          "folk",
    "соул":          "soul",
    "классика":      "classical",
    "электронная":   "electronic",
    "r&b":           "r&b",
    "шансон":        "chanson",
    "балада":        "ballad",
    "баллада":       "ballad",
    "блюз":          "blues",
    "метал":         "metal",
    "металл":        "metal",
    "панк":          "punk",
    "регги":         "reggae",
    "хип-хоп":       "hip-hop",
    "хипхоп":        "hip-hop",
}


def _normalize_lyrics(lyrics: str) -> str:
    """Заменяет русские структурные теги на английские, которые понимает Suno."""
    def replace_tag(m):
        inner = m.group(1).strip().lower()
        return f"[{_TAG_MAP.get(inner, m.group(1).strip())}]"
    return re.sub(r'\[([^\]]+)\]', replace_tag, lyrics)


def _normalize_style(style: str) -> str:
    """Переводит русские жанры в английские; название группы оставляет как есть.
    Разделяем ТОЛЬКО по запятой — деление ещё и по "/" ломало теги вроде "4/4 beat" или "1980s/90s"."""
    parts = [p.strip() for p in style.split(",") if p.strip()]
    result = []
    for p in parts:
        result.append(_STYLE_MAP.get(p.lower(), p))
    return ", ".join(result)


async def generate_song(lyrics: str, style: str, title: str) -> str:
    headers = {
        "Authorization": f"Bearer {KIE_API_KEY}",
        "Content-Type": "application/json",
    }

    clean_lyrics = _normalize_lyrics(lyrics)
    clean_style = _normalize_style(style)

    payload = {
        "prompt": clean_lyrics,
        "style": clean_style,
        "title": title[:80],
        "customMode": True,
        "instrumental": False,
        "model": "V4_5",
        "callBackUrl": "https://httpbin.org/post",
    }

    async with aiohttp.ClientSession() as session:
        # Запускаем генерацию
        async with session.post(
            f"{KIE_BASE_URL}/api/v1/generate",
            headers=headers,
            json=payload,
        ) as resp:
            resp.raise_for_status()
            result = await resp.json()

        if result.get("code") != 200:
            raise ValueError(f"KIE ошибка при создании задачи: {result}")

        task_id = result.get("data", {}).get("taskId") or result.get("data", {}).get("task_id")
        if not task_id:
            raise ValueError(f"KIE не вернул taskId. Ответ: {result}")

        # Поллим статус
        elapsed = 0
        while elapsed < MAX_WAIT:
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

            async with session.get(
                f"{KIE_BASE_URL}/api/v1/generate/record-info",
                headers=headers,
                params={"taskId": task_id},
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

            if data.get("code") != 200:
                raise RuntimeError(f"Ошибка при получении статуса: {data}")

            status = (data.get("data") or {}).get("status", "")

            if status in ERROR_STATUSES:
                raise RuntimeError(f"KIE вернул ошибку генерации: {status}")

            if status == "SUCCESS":
                inner = (data.get("data") or {}).get("response") or {}
                tracks = inner.get("sunoData") or []
                for track in tracks:
                    url = (track.get("audioUrl")
                           or track.get("sourceAudioUrl")
                           or track.get("streamAudioUrl"))
                    if url:
                        return url
                raise ValueError(f"Статус SUCCESS, но audioUrl не найден. Ответ: {data}")

        raise TimeoutError(f"Suno не успел сгенерировать трек за {MAX_WAIT} секунд")
