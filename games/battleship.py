import random

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

SIZE = 6  # поле 6x6 — заметно больше, чем раньше
SHIPS_COUNT = 6  # 6 однопалубных кораблей у каждого игрока

UNKNOWN = "🟦"
HIT = "🚢"   # попадание — виден найденный корабль
MISS = "❌"  # промах — крест

# Шанс, что после выстрела одна из старых отметок на своём поле обстрела
# затянется "туманом войны" и снова станет неизвестной (можно перепутать
# и выстрелить туда ещё раз).
FADE_CHANCE = 0.22


def new_ships() -> set[int]:
    return set(random.sample(range(SIZE * SIZE), SHIPS_COUNT))


def new_round_state(p1_id: int, p2_id: int) -> dict:
    return {
        "ships": {p1_id: new_ships(), p2_id: new_ships()},
        "shots": {p1_id: {}, p2_id: {}},  # shots[attacker_id][cell] = "hit"/"miss"
    }


def register_shot(bs: dict, attacker_id: int, idx: int, is_hit: bool) -> None:
    """Фиксирует результат выстрела и с небольшим шансом скрывает туманом
    одну из ранее открытых клеток (кроме только что выстреленной)."""
    shots = bs["shots"][attacker_id]
    shots[idx] = "hit" if is_hit else "miss"

    if random.random() < FADE_CHANCE:
        candidates = [i for i in shots if i != idx]
        if candidates:
            del shots[random.choice(candidates)]


def build_keyboard(bs: dict, attacker_id: int) -> InlineKeyboardMarkup:
    my_shots = bs["shots"][attacker_id]
    rows = []
    for r in range(SIZE):
        row = []
        for c in range(SIZE):
            i = r * SIZE + c
            mark = my_shots.get(i)
            emoji = HIT if mark == "hit" else MISS if mark == "miss" else UNKNOWN
            row.append(InlineKeyboardButton(text=emoji, callback_data=f"bs:{i}"))
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
        f"Осталось кораблей у {defender_name}: <b>{left}</b>\n"
        f"🎯 Попал — стреляешь ещё раз. 🌫 Туман иногда скрывает старые метки."
        + (f"\n\n{note}" if note else "")
    )
