"""
Простое хранилище состояния партий в памяти процесса.

ВАЖНО: на бесплатном Render процесс может перезапуститься (redeploy,
падение, ручной рестарт) — при этом все текущие партии потеряются.
Для прод-версии замените этот словарь на Redis (Render предоставляет
бесплатный Key Value на 25 МБ) — интерфейс ниже специально сделан
таким, чтобы это было легко сделать (get/set/delete по одному ключу).
"""

from typing import Optional

_games: dict[str, dict] = {}


def get(inline_message_id: str) -> Optional[dict]:
    return _games.get(inline_message_id)


def set(inline_message_id: str, data: dict) -> None:
    _games[inline_message_id] = data


def delete(inline_message_id: str) -> None:
    _games.pop(inline_message_id, None)
