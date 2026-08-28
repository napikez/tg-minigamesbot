import random

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

SIZE = 16
EMOJI_POOL = ["🍎", "🍌", "🍇", "🍉", "🍒", "🥑", "🍍", "🥕", "🌽", "🍓", "🍑", "🥝"]
HIDDEN = "❓"


def new_round_state() -> dict:
    symbols = random.sample(EMOJI_POOL, SIZE // 2) * 2
    random.shuffle(symbols)
    return {
        "cards": symbols,
        "matched": set(),
        "pending": [],
        "locked": False,
        "pairs": {},
        "round_seq": 0,
    }


def build_keyboard(mem: dict) -> InlineKeyboardMarkup:
    rows = []
    for r in range(4):
        row = []
        for c in range(4):
            i = r * 4 + c
            if i in mem["matched"] or i in mem["pending"]:
                text = mem["cards"][i]
            else:
                text = HIDDEN
            row.append(InlineKeyboardButton(text=text, callback_data=f"mem:{i}"))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_text(state: dict, note: str = "") -> str:
    p1, p2 = state["p1_name"], state["p2_name"]
    s1, s2 = state["score"][state["p1_id"]], state["score"][state["p2_id"]]
    mem = state["memory"]
    turn_name = p1 if state["turn_id"] == state["p1_id"] else p2
    pairs1 = mem["pairs"].get(state["p1_id"], 0)
    pairs2 = mem["pairs"].get(state["p2_id"], 0)
    header = f"🧠 {p1} <b>{s1}</b> : <b>{s2}</b> {p2}"
    return (
        f"{header}\n\n"
        f"Найдено пар: {p1} — {pairs1}, {p2} — {pairs2}\n"
        f"Ходит: <b>{turn_name}</b>" + (f"\n\n{note}" if note else "")
    )
