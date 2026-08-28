from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

EMPTY = " "
SYMBOLS = {"X": "❌", "O": "⭕", EMPTY: "▫️"}

WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]


def new_board() -> list[str]:
    return [EMPTY] * 9


def check_winner(board: list[str]) -> str | None:
    for a, b, c in WIN_LINES:
        if board[a] != EMPTY and board[a] == board[b] == board[c]:
            return board[a]
    return None


def is_draw(board: list[str]) -> bool:
    return EMPTY not in board and check_winner(board) is None


def build_keyboard(board: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            row.append(
                InlineKeyboardButton(text=SYMBOLS[board[i]], callback_data=f"ttt:{i}")
            )
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_text(state: dict) -> str:
    p1, p2 = state["p1_name"], state["p2_name"]
    s1, s2 = state["score"][state["p1_id"]], state["score"][state["p2_id"]]
    turn_id = state["turn_id"]
    turn_name = p1 if turn_id == state["p1_id"] else p2
    header = f"❌ {p1} <b>{s1}</b> : <b>{s2}</b> {p2} ⭕"
    return f"{header}\n\nХодит: <b>{turn_name}</b>"
