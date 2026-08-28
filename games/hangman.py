import random

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

WORDS = [
    "РАКЕТА", "САМОЛЕТ", "КОМПЬЮТЕР", "ГИТАРА", "ВУЛКАН", "ОБЛАКО",
    "ЖИРАФ", "ПИНГВИН", "БИБЛИОТЕКА", "ФУТБОЛ", "ШОКОЛАД", "ВЕЛОСИПЕД",
    "ОКЕАН", "ЗВЕЗДА", "МЕДВЕДЬ", "КАРТА", "ТЕЛЕФОН", "ОСТРОВ",
    "ДРАКОН", "МОСТ", "ПОЕЗД", "ЛАБИРИНТ", "ФОНАРЬ", "КОРАБЛЬ",
]

ALPHABET = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЬЫЭЮЯ"
MAX_WRONG = 6
STAGES = ["🙂", "😐", "😟", "😨", "😱", "💀", "☠️"]


def new_round_state() -> dict:
    return {"word": random.choice(WORDS), "guessed": set(), "wrong": 0}


def masked_word(hm: dict) -> str:
    return " ".join(ch if ch in hm["guessed"] else "▢" for ch in hm["word"])


def build_keyboard(hm: dict) -> InlineKeyboardMarkup:
    remaining = [ch for ch in ALPHABET if ch not in hm["guessed"]]
    rows = []
    row = []
    for i, ch in enumerate(remaining, start=1):
        row.append(InlineKeyboardButton(text=ch, callback_data=f"hm:{ch}"))
        if i % 8 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_text(state: dict, note: str = "") -> str:
    p1, p2 = state["p1_name"], state["p2_name"]
    s1, s2 = state["score"][state["p1_id"]], state["score"][state["p2_id"]]
    hm = state["hangman"]
    turn_name = p1 if state["turn_id"] == state["p1_id"] else p2
    header = f"🔤 {p1} <b>{s1}</b> : <b>{s2}</b> {p2}"
    stage = STAGES[min(hm["wrong"], MAX_WRONG)]
    return (
        f"{header}\n\n"
        f"{stage} Слово: <b>{masked_word(hm)}</b>\n"
        f"Ошибок: {hm['wrong']}/{MAX_WRONG}\n"
        f"Ходит: <b>{turn_name}</b>" + (f"\n\n{note}" if note else "")
    )
