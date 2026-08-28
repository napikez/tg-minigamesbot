import random

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

SIZE = 4
SHIPS_COUNT = 3

UNKNOWN = "🟦"
HIT = "🔥"
MISS = "⚪"


def new_ships() -> set[int]:
    return set(random.sample(range(SIZE * SIZE), SHIPS_COUNT))


def new_round_state(p1_id: int, p2_id: int) -> dict:
    return {
        "ships": {p1_id: new_ships(), p2_id: new_ships()},
        "shots": {p1_id: {}, p2_id: {}},
    }


def build_keyboard(bs: dict, attacker_id: int) -> InlineKeyboardMarkup:
    my_shots = bs["shots"][attacker_id]
    rows = []
    for r in range(SIZE):
        row = []
        for c in range(SIZE):
            i = r * SIZE + c
            mark = my_shots.get(i, UNKNOWN)
            row.append(InlineKeyboardButton(text=mark, callback_data=f"bs:{i}"))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_text(state: dict, note: str = "") -> str:
    p1, p2 = state["p1_name"], state["p2_name"]
    s1, s2 = state["score"][state["p1_id"]], state["score"][state["p2_id"]]
    bs = state["battleship"]
    attacker_id = state["turn_id"]
    attacker_name = p1 if attacker_id == state["p1_id"] else p2
    defender_id = state["p2_id"] if attacker_id == state["p1_id"] else state["p1_id"]
    defender_name = p2 if defender_id == state["p2_id"] else p1
    left = len(bs["ships"][defender_id])
    header = f"🚢 {p1} <b>{s1}</b> : <b>{s2}</b> {p2}"
    return (
        f"{header}\n\n"
        f"Стреляет: <b>{attacker_name}</b> по флоту игрока <b>{defender_name}</b>\n"
        f"Осталось кораблей у {defender_name}: <b>{left}</b>"
        + (f"\n\n{note}" if note else "")
    )
