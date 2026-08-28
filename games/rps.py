from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

EMOJI = {"r": "🪨", "p": "📄", "s": "✂️"}
BEATS = {"r": "s", "s": "p", "p": "r"}


def build_keyboard() -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(text="🪨 Камень", callback_data="rps:r"),
        InlineKeyboardButton(text="📄 Бумага", callback_data="rps:p"),
        InlineKeyboardButton(text="✂️ Ножницы", callback_data="rps:s"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row])


def round_winner(pick1: str, pick2: str) -> int:
    if pick1 == pick2:
        return 0
    return 1 if BEATS[pick1] == pick2 else 2


def build_text(state: dict, round_result: str | None = None) -> str:
    p1, p2 = state["p1_name"], state["p2_name"]
    s1, s2 = state["score"][state["p1_id"]], state["score"][state["p2_id"]]
    header = f"🪨✂️📄 {p1} <b>{s1}</b> : <b>{s2}</b> {p2}"
    picked = state["round_picks"]
    waiting = []
    if state["p1_id"] not in picked:
        waiting.append(p1)
    if state["p2_id"] not in picked:
        waiting.append(p2)
    body = round_result or (
        f"Ждём выбор: <b>{', '.join(waiting)}</b>" if waiting else "Считаем..."
    )
    return f"{header}\n\n{body}"
