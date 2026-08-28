from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

COLS = 7
ROWS = 6
EMPTY = " "
SYMBOLS = {"X": "🔴", "O": "🟡", EMPTY: "⚪"}
COL_LABELS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]


def new_board() -> list[str]:
    return [EMPTY] * (ROWS * COLS)


def _idx(row: int, col: int) -> int:
    return row * COLS + col


def drop(board: list[str], col: int, symbol: str) -> int | None:
    for row in range(ROWS - 1, -1, -1):
        if board[_idx(row, col)] == EMPTY:
            board[_idx(row, col)] = symbol
            return row
    return None


def check_winner(board: list[str]) -> str | None:
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for row in range(ROWS):
        for col in range(COLS):
            symbol = board[_idx(row, col)]
            if symbol == EMPTY:
                continue
            for dr, dc in directions:
                cells = [(row + dr * k, col + dc * k) for k in range(4)]
                if all(0 <= r < ROWS and 0 <= c < COLS for r, c in cells):
                    if all(board[_idx(r, c)] == symbol for r, c in cells):
                        return symbol
    return None


def is_full(board: list[str]) -> bool:
    return EMPTY not in board


def build_keyboard() -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=lbl, callback_data=f"c4:{i}") for i, lbl in enumerate(COL_LABELS)]
    return InlineKeyboardMarkup(inline_keyboard=[row])


def render_board(board: list[str]) -> str:
    lines = []
    for row in range(ROWS):
        line = "".join(SYMBOLS[board[_idx(row, col)]] for col in range(COLS))
        lines.append(line)
    return "\n".join(lines)


def build_text(state: dict, note: str = "") -> str:
    p1, p2 = state["p1_name"], state["p2_name"]
    s1, s2 = state["score"][state["p1_id"]], state["score"][state["p2_id"]]
    turn_name = p1 if state["turn_id"] == state["p1_id"] else p2
    header = f"🔴 {p1} <b>{s1}</b> : <b>{s2}</b> {p2} 🟡"
    board_text = render_board(state["board"])
    return f"{header}\n\n{board_text}\n\nХодит: <b>{turn_name}</b>" + (f"\n\n{note}" if note else "")
