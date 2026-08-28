import random

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

CUPS = 4
HIDDEN = "❔"
EMPTY = "⬜"


def new_round_state() -> dict:
    return {"secret": random.randint(0, CUPS - 1), "revealed_empty": set()}


def build_keyboard(shell: dict) -> InlineKeyboardMarkup:
    row = []
    for i in range(CUPS):
        text = EMPTY if i in shell["revealed_empty"] else HIDDEN
        row.append(InlineKeyboardButton(text=text, callback_data=f"shell:{i}"))
    return InlineKeyboardMarkup(inline_keyboard=[row])


def build_text(state: dict, note: str = "") -> str:
    p1, p2 = state["p1_name"], state["p2_name"]
    s1, s2 = state["score"][state["p1_id"]], state["score"][state["p2_id"]]
    turn_name = p1 if state["turn_id"] == state["p1_id"] else p2
    header = f"🎯 {p1} <b>{s1}</b> : <b>{s2}</b> {p2}"
    return (
        f"{header}\n\nПод одной из чашек спрятан шарик 🔴. Угадывает: <b>{turn_name}</b>"
        + (f"\n\n{note}" if note else "")
    )
