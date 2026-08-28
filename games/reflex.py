import random

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

MIN_DELAY = 2.0
MAX_DELAY = 5.0


def random_delay() -> float:
    return random.uniform(MIN_DELAY, MAX_DELAY)


def build_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔴 Жми!", callback_data="reflex:press")]]
    )


def build_text_waiting(state: dict) -> str:
    p1, p2 = state["p1_name"], state["p2_name"]
    s1, s2 = state["score"][state["p1_id"]], state["score"][state["p2_id"]]
    header = f"⚡ {p1} <b>{s1}</b> : <b>{s2}</b> {p2}"
    return f"{header}\n\nПриготовьтесь... не жмите раньше времени!"


def build_text_armed(state: dict) -> str:
    p1, p2 = state["p1_name"], state["p2_name"]
    s1, s2 = state["score"][state["p1_id"]], state["score"][state["p2_id"]]
    header = f"⚡ {p1} <b>{s1}</b> : <b>{s2}</b> {p2}"
    return f"{header}\n\n🚨 ЖМИ СЕЙЧАС! 🚨"
