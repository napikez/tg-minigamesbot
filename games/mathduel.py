import random

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def _generate_question() -> tuple[str, int]:
    op = random.choice(["+", "-", "×"])
    if op == "+":
        a, b = random.randint(2, 50), random.randint(2, 50)
        return f"{a} + {b}", a + b
    if op == "-":
        a, b = random.randint(10, 60), random.randint(1, 9)
        a, b = max(a, b), min(a, b)
        return f"{a} - {b}", a - b
    a, b = random.randint(2, 12), random.randint(2, 9)
    return f"{a} × {b}", a * b


def new_round_state() -> dict:
    question, correct = _generate_question()
    options = {correct}
    while len(options) < 4:
        delta = random.choice([-5, -3, -2, -1, 1, 2, 3, 5])
        candidate = correct + delta
        if candidate > 0:
            options.add(candidate)
    options = list(options)
    random.shuffle(options)
    return {
        "question": question,
        "correct": correct,
        "options": options,
        "eliminated": set(),
    }


def build_keyboard(md: dict) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i, value in enumerate(md["options"]):
        if i in md["eliminated"]:
            continue
        row.append(InlineKeyboardButton(text=str(value), callback_data=f"math:{i}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_text(state: dict, note: str = "") -> str:
    p1, p2 = state["p1_name"], state["p2_name"]
    s1, s2 = state["score"][state["p1_id"]], state["score"][state["p2_id"]]
    md = state["mathduel"]
    header = f"➗ {p1} <b>{s1}</b> : <b>{s2}</b> {p2}"
    return f"{header}\n\nСколько будет: <b>{md['question']}</b> ?\nЖмите правильный ответ первыми!" + (
        f"\n\n{note}" if note else ""
    )
