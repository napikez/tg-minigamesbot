import random

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

DIGITS = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}


def build_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎲 Бросить кубик", callback_data="dice:roll")]]
    )


def roll() -> int:
    return random.randint(1, 6)


def build_text(state: dict, round_result: str | None = None) -> str:
    p1, p2 = state["p1_name"], state["p2_name"]
    s1, s2 = state["score"][state["p1_id"]], state["score"][state["p2_id"]]
    header = f"🎲 {p1} <b>{s1}</b> : <b>{s2}</b> {p2}"
    rolls = state["round_rolls"]
    waiting = []
    if state["p1_id"] not in rolls:
        waiting.append(p1)
    if state["p2_id"] not in rolls:
        waiting.append(p2)
    body = round_result or (
        f"Ждём бросок: <b>{', '.join(waiting)}</b>" if waiting else "Считаем..."
    )
    return f"{header}\n\n{body}"
