import json
import os
from config import ADMIN_ID

_DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "users.json")

TRIAL_LIMIT = 3  # бесплатных песен на пользователя


def _load() -> dict:
    os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
    if not os.path.exists(_DATA_FILE):
        return {}
    with open(_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
    with open(_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def _songs_used(record: dict) -> int:
    """Совместимость со старым форматом {"trial_used": true} — считаем как 1 использованную песню."""
    if "songs_used" in record:
        return record["songs_used"]
    return 1 if record.get("trial_used") else 0


def trial_available(user_id: int) -> bool:
    """True если у пользователя ещё остались бесплатные песни (лимит — TRIAL_LIMIT)."""
    if is_admin(user_id):
        return True
    data = _load()
    return _songs_used(data.get(str(user_id), {})) < TRIAL_LIMIT


def songs_left(user_id: int) -> int:
    """Сколько бесплатных песен ещё осталось у пользователя."""
    if is_admin(user_id):
        return TRIAL_LIMIT
    data = _load()
    return max(0, TRIAL_LIMIT - _songs_used(data.get(str(user_id), {})))


def mark_trial_used(user_id: int) -> None:
    """Учитывает использование одной бесплатной песни."""
    if is_admin(user_id):
        return
    data = _load()
    key = str(user_id)
    record = data.setdefault(key, {})
    record["songs_used"] = _songs_used(record) + 1
    record.pop("trial_used", None)  # чистим старый формат
    _save(data)
