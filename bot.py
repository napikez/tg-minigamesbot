import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    InlineQuery,
    ChosenInlineResult,
    CallbackQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

import storage
from games import GAMES, WIN_SCORE
from games import tictactoe, rps, dice, battleship, connect4, reflex, shell, hangman, mathduel, memory

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gamebot")

def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Переменная окружения {name} не задана. "
            f"Проверьте Render → Environment → {name}."
        )
    return value


BOT_TOKEN = _require_env("BOT_TOKEN")
WEBHOOK_HOST = _require_env("WEBHOOK_URL").rstrip("/")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
PORT = int(os.environ.get("PORT", 10000))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------- /start ----------

@dp.message(CommandStart())
async def start(message: Message):
    me = await bot.me()
    await message.answer(
        "🎮 Я бот для мини-игр между двумя игроками.\n\n"
        "Чтобы вызвать друга, напиши в любом чате:\n"
        f"<code>@{me.username} username_друга</code>\n\n"
        "Появится список игр — выбери одну, друг примет вызов кнопкой "
        f"и начнётся матч до {WIN_SCORE} побед!",
        parse_mode="HTML",
    )


# ---------- inline: выбор игры ----------

@dp.inline_query()
async def inline_handler(iq: InlineQuery):
    opponent = iq.query.strip().lstrip("@").strip()

    if not opponent:
        await iq.answer(
            [
                InlineQueryResultArticle(
                    id="help",
                    title="Напиши username соперника",
                    description="Например: friend_username",
                    input_message_content=InputTextMessageContent(
                        message_text="Чтобы вызвать на игру, напиши: @имя_бота username_соперника"
                    ),
                )
            ],
            cache_time=1,
            is_personal=True,
        )
        return

    results = []
    for code, title in GAMES.items():
        text = (
            f"🎮 <b>{iq.from_user.full_name}</b> вызывает "
            f"<b>@{opponent}</b> на игру:\n{title}\n\n"
            f"Нажми «Принять вызов», чтобы начать матч до {WIN_SCORE} побед!"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Принять вызов", callback_data=f"acc:{code}:{opponent}")]
            ]
        )
        results.append(
            InlineQueryResultArticle(
                id=code,
                title=title,
                description=f"Вызвать @{opponent}",
                input_message_content=InputTextMessageContent(message_text=text, parse_mode="HTML"),
                reply_markup=keyboard,
            )
        )
    await iq.answer(results, cache_time=1, is_personal=True)


# ---------- фиксируем, кто и кого вызвал ----------

@dp.chosen_inline_result()
async def chosen_handler(res: ChosenInlineResult):
    code = res.result_id
    if code not in GAMES:
        return
    opponent = res.query.strip().lstrip("@").strip().lower()
    storage.set(
        res.inline_message_id,
        {
            "game": code,
            "status": "pending",
            "p1_id": res.from_user.id,
            "p1_name": res.from_user.full_name,
            "opponent_username": opponent,
            "p2_id": None,
            "p2_name": None,
            "score": {},
        },
    )


def _init_round(state: dict, code: str) -> tuple[str, InlineKeyboardMarkup]:
    """Инициализирует состояние нового раунда конкретной игры и возвращает (текст, клавиатура)."""
    if code == "ttt":
        state["board"] = tictactoe.new_board()
        state["turn_id"] = state["p1_id"]
        return tictactoe.build_text(state), tictactoe.build_keyboard(state["board"])

    if code == "rps":
        state["round_picks"] = {}
        return rps.build_text(state), rps.build_keyboard()

    if code == "dice":
        state["round_rolls"] = {}
        return dice.build_text(state), dice.build_keyboard()

    if code == "bs":
        state["turn_id"] = state["p1_id"]
        state["battleship"] = battleship.new_round_state(state["p1_id"], state["p2_id"])
        return battleship.build_text(state), battleship.build_keyboard(state["battleship"], state["turn_id"])

    if code == "c4":
        state["board"] = connect4.new_board()
        state["turn_id"] = state["p1_id"]
        return connect4.build_text(state), connect4.build_keyboard()

    if code == "reflex":
        state["round_seq"] = state.get("round_seq", 0) + 1
        state["armed"] = False
        state["round_resolved"] = False
        return reflex.build_text_waiting(state), reflex.build_keyboard()

    if code == "shell":
        state["turn_id"] = state["p1_id"]
        state["shell"] = shell.new_round_state()
        return shell.build_text(state), shell.build_keyboard(state["shell"])

    if code == "hangman":
        state["turn_id"] = state["p1_id"]
        state["hangman"] = hangman.new_round_state()
        return hangman.build_text(state), hangman.build_keyboard(state["hangman"])

    if code == "math":
        state["mathduel"] = mathduel.new_round_state()
        return mathduel.build_text(state), mathduel.build_keyboard(state["mathduel"])

    if code == "memory":
        state["turn_id"] = state["p1_id"]
        state["memory"] = memory.new_round_state()
        state["memory"]["pairs"] = {state["p1_id"]: 0, state["p2_id"]: 0}
        return memory.build_text(state), memory.build_keyboard(state["memory"])

    raise ValueError(f"unknown game code: {code}")


# ---------- принятие вызова ----------

@dp.callback_query(F.data.startswith("acc:"))
async def accept_handler(cq: CallbackQuery):
    _, code, opponent = cq.data.split(":", 2)
    inline_message_id = cq.inline_message_id
    state = storage.get(inline_message_id)

    if not state:
        await cq.answer("Вызов устарел. Создайте новый через инлайн-режим.", show_alert=True)
        return
    if state["status"] != "pending":
        await cq.answer("Игра уже началась.", show_alert=True)
        return
    if cq.from_user.id == state["p1_id"]:
        await cq.answer("Нельзя играть самому с собой 🙂", show_alert=True)
        return
    presser_username = (cq.from_user.username or "").lower()
    if presser_username != state["opponent_username"]:
        await cq.answer("Этот вызов не для тебя 🙂", show_alert=True)
        return

    state["p2_id"] = cq.from_user.id
    state["p2_name"] = cq.from_user.full_name
    state["status"] = "active"
    state["score"] = {state["p1_id"]: 0, state["p2_id"]: 0}

    text, keyboard = _init_round(state, code)
    storage.set(inline_message_id, state)
    await bot.edit_message_text(text, inline_message_id=inline_message_id, reply_markup=keyboard, parse_mode="HTML")
    await cq.answer()

    if code == "reflex":
        asyncio.create_task(_schedule_reflex_arm(inline_message_id, state["round_seq"]))


def _finish_check(state: dict) -> tuple[bool, str | None]:
    for pid, score in state["score"].items():
        if score >= WIN_SCORE:
            name = state["p1_name"] if pid == state["p1_id"] else state["p2_name"]
            return True, name
    return False, None


async def _end_round_or_finish(inline_message_id: str, state: dict, code: str, suffix: str, build_text_fn, keyboard):
    """Общая обёртка: проверяет завершение матча, иначе показывает суффикс раунда."""
    finished, winner_name = _finish_check(state)
    storage.set(inline_message_id, state)
    if finished:
        text = f"{build_text_fn(state)}{suffix}\n\n🏆 Победа: <b>{winner_name}</b>! Матч окончен."
        await bot.edit_message_text(text, inline_message_id=inline_message_id, parse_mode="HTML")
        storage.delete(inline_message_id)
    else:
        text = build_text_fn(state) + suffix
        await bot.edit_message_text(text, inline_message_id=inline_message_id, reply_markup=keyboard, parse_mode="HTML")
        if code == "reflex":
            asyncio.create_task(_schedule_reflex_arm(inline_message_id, state["round_seq"]))


# ---------- крестики-нолики ----------

@dp.callback_query(F.data.startswith("ttt:"))
async def ttt_move(cq: CallbackQuery):
    state = storage.get(cq.inline_message_id)
    if not state or state.get("status") != "active" or state["game"] != "ttt":
        await cq.answer()
        return
    if cq.from_user.id not in (state["p1_id"], state["p2_id"]):
        await cq.answer("Это не твоя игра 🙂", show_alert=True)
        return
    if cq.from_user.id != state["turn_id"]:
        await cq.answer("Сейчас не твой ход", show_alert=True)
        return

    idx = int(cq.data.split(":")[1])
    board = state["board"]
    if board[idx] != tictactoe.EMPTY:
        await cq.answer("Клетка занята", show_alert=True)
        return

    symbol = "X" if cq.from_user.id == state["p1_id"] else "O"
    board[idx] = symbol
    winner_symbol = tictactoe.check_winner(board)
    suffix = ""

    if winner_symbol:
        winner_id = state["p1_id"] if winner_symbol == "X" else state["p2_id"]
        winner_name = state["p1_name"] if winner_symbol == "X" else state["p2_name"]
        state["score"][winner_id] += 1
        state["board"] = tictactoe.new_board()
        state["turn_id"] = state["p2_id"] if winner_id == state["p1_id"] else state["p1_id"]
        suffix = f"\n\n🎉 Раунд выиграл(а) <b>{winner_name}</b>! Новый раунд."
    elif tictactoe.is_draw(board):
        state["board"] = tictactoe.new_board()
        state["turn_id"] = state["p2_id"] if state["turn_id"] == state["p1_id"] else state["p1_id"]
        suffix = "\n\n🤝 Ничья! Новый раунд."
    else:
        state["turn_id"] = state["p2_id"] if cq.from_user.id == state["p1_id"] else state["p1_id"]

    await cq.answer()
    keyboard = tictactoe.build_keyboard(state["board"])
    await _end_round_or_finish(cq.inline_message_id, state, "ttt", suffix, tictactoe.build_text, keyboard)


# ---------- камень-ножницы-бумага ----------

@dp.callback_query(F.data.startswith("rps:"))
async def rps_move(cq: CallbackQuery):
    state = storage.get(cq.inline_message_id)
    if not state or state.get("status") != "active" or state["game"] != "rps":
        await cq.answer()
        return
    if cq.from_user.id not in (state["p1_id"], state["p2_id"]):
        await cq.answer("Это не твоя игра 🙂", show_alert=True)
        return

    pick = cq.data.split(":")[1]
    picks = state["round_picks"]
    if cq.from_user.id in picks:
        await cq.answer("Ты уже выбрал(а) в этом раунде", show_alert=True)
        return

    picks[cq.from_user.id] = pick
    await cq.answer(f"Ты выбрал(а) {rps.EMOJI[pick]}")

    if len(picks) < 2:
        storage.set(cq.inline_message_id, state)
        await bot.edit_message_text(
            rps.build_text(state), inline_message_id=cq.inline_message_id,
            reply_markup=rps.build_keyboard(), parse_mode="HTML",
        )
        return

    p1_pick, p2_pick = picks[state["p1_id"]], picks[state["p2_id"]]
    result = rps.round_winner(p1_pick, p2_pick)
    line = f"{state['p1_name']}: {rps.EMOJI[p1_pick]}  vs  {rps.EMOJI[p2_pick]} :{state['p2_name']}"

    if result == 0:
        round_text = f"{line}\n\n🤝 Ничья в раунде!"
    else:
        winner_id = state["p1_id"] if result == 1 else state["p2_id"]
        winner_name = state["p1_name"] if result == 1 else state["p2_name"]
        state["score"][winner_id] += 1
        round_text = f"{line}\n\n🎉 Раунд выиграл(а) {winner_name}!"

    state["round_picks"] = {}
    finished, name = _finish_check(state)
    storage.set(cq.inline_message_id, state)

    if finished:
        text = f"{rps.build_text(state, round_text)}\n\n🏆 Победа: <b>{name}</b>! Матч окончен."
        await bot.edit_message_text(text, inline_message_id=cq.inline_message_id, parse_mode="HTML")
        storage.delete(cq.inline_message_id)
    else:
        text = rps.build_text(state, round_text)
        await bot.edit_message_text(
            text, inline_message_id=cq.inline_message_id, reply_markup=rps.build_keyboard(), parse_mode="HTML"
        )


# ---------- дуэль кубиков ----------

@dp.callback_query(F.data == "dice:roll")
async def dice_move(cq: CallbackQuery):
    state = storage.get(cq.inline_message_id)
    if not state or state.get("status") != "active" or state["game"] != "dice":
        await cq.answer()
        return
    if cq.from_user.id not in (state["p1_id"], state["p2_id"]):
        await cq.answer("Это не твоя игра 🙂", show_alert=True)
        return

    rolls = state["round_rolls"]
    if cq.from_user.id in rolls:
        await cq.answer("Ты уже бросил(а) кубик в этом раунде", show_alert=True)
        return

    value = dice.roll()
    rolls[cq.from_user.id] = value
    await cq.answer(f"Выпало: {value}")

    if len(rolls) < 2:
        storage.set(cq.inline_message_id, state)
        await bot.edit_message_text(
            dice.build_text(state), inline_message_id=cq.inline_message_id,
            reply_markup=dice.build_keyboard(), parse_mode="HTML",
        )
        return

    v1, v2 = rolls[state["p1_id"]], rolls[state["p2_id"]]
    line = f"{state['p1_name']}: {dice.DIGITS[v1]} ({v1})  vs  ({v2}) {dice.DIGITS[v2]} :{state['p2_name']}"

    if v1 == v2:
        round_text = f"{line}\n\n🤝 Ничья, переброс раунда!"
    else:
        winner_id = state["p1_id"] if v1 > v2 else state["p2_id"]
        winner_name = state["p1_name"] if v1 > v2 else state["p2_name"]
        state["score"][winner_id] += 1
        round_text = f"{line}\n\n🎉 Раунд выиграл(а) {winner_name}!"

    state["round_rolls"] = {}
    finished, name = _finish_check(state)
    storage.set(cq.inline_message_id, state)

    if finished:
        text = f"{dice.build_text(state, round_text)}\n\n🏆 Победа: <b>{name}</b>! Матч окончен."
        await bot.edit_message_text(text, inline_message_id=cq.inline_message_id, parse_mode="HTML")
        storage.delete(cq.inline_message_id)
    else:
        text = dice.build_text(state, round_text)
        await bot.edit_message_text(
            text, inline_message_id=cq.inline_message_id, reply_markup=dice.build_keyboard(), parse_mode="HTML"
        )


# ---------- морской бой ----------

@dp.callback_query(F.data.startswith("bs:"))
async def battleship_move(cq: CallbackQuery):
    state = storage.get(cq.inline_message_id)
    if not state or state.get("status") != "active" or state["game"] != "bs":
        await cq.answer()
        return
    if cq.from_user.id not in (state["p1_id"], state["p2_id"]):
        await cq.answer("Это не твоя игра 🙂", show_alert=True)
        return
    if cq.from_user.id != state["turn_id"]:
        await cq.answer("Сейчас не твой ход", show_alert=True)
        return

    idx = int(cq.data.split(":")[1])
    bs = state["battleship"]
    attacker_id = state["turn_id"]
    defender_id = state["p2_id"] if attacker_id == state["p1_id"] else state["p1_id"]

    if idx in bs["shots"][attacker_id]:
        await cq.answer("Сюда уже стреляли", show_alert=True)
        return

    suffix = ""
    if idx in bs["ships"][defender_id]:
        bs["shots"][attacker_id][idx] = "hit"
        bs["ships"][defender_id].discard(idx)
        await cq.answer("Попадание! 🔥")
        if not bs["ships"][defender_id]:
            attacker_name = state["p1_name"] if attacker_id == state["p1_id"] else state["p2_name"]
            state["score"][attacker_id] += 1
            suffix = f"\n\n🎉 Весь флот потоплен! Раунд выиграл(а) <b>{attacker_name}</b>. Новый раунд."
            finished, _ = _finish_check(state)
            if not finished:
                _init_round(state, "bs")
                bs = state["battleship"]  # ссылка на локальную переменную устарела после ре-инициализации
        else:
            state["turn_id"] = defender_id
    else:
        bs["shots"][attacker_id][idx] = "miss"
        await cq.answer("Мимо 💦")
        state["turn_id"] = defender_id

    keyboard = battleship.build_keyboard(bs, state["turn_id"])
    await _end_round_or_finish(cq.inline_message_id, state, "bs", suffix, battleship.build_text, keyboard)


# ---------- четыре в ряд ----------

@dp.callback_query(F.data.startswith("c4:"))
async def connect4_move(cq: CallbackQuery):
    state = storage.get(cq.inline_message_id)
    if not state or state.get("status") != "active" or state["game"] != "c4":
        await cq.answer()
        return
    if cq.from_user.id not in (state["p1_id"], state["p2_id"]):
        await cq.answer("Это не твоя игра 🙂", show_alert=True)
        return
    if cq.from_user.id != state["turn_id"]:
        await cq.answer("Сейчас не твой ход", show_alert=True)
        return

    col = int(cq.data.split(":")[1])
    board = state["board"]
    symbol = "X" if cq.from_user.id == state["p1_id"] else "O"
    placed_row = connect4.drop(board, col, symbol)
    if placed_row is None:
        await cq.answer("Колонка заполнена", show_alert=True)
        return

    winner_symbol = connect4.check_winner(board)
    suffix = ""
    await cq.answer()

    if winner_symbol:
        winner_id = state["p1_id"] if winner_symbol == "X" else state["p2_id"]
        winner_name = state["p1_name"] if winner_symbol == "X" else state["p2_name"]
        state["score"][winner_id] += 1
        state["board"] = connect4.new_board()
        state["turn_id"] = state["p2_id"] if winner_id == state["p1_id"] else state["p1_id"]
        suffix = f"\n\n🎉 Раунд выиграл(а) <b>{winner_name}</b>! Новый раунд."
    elif connect4.is_full(board):
        state["board"] = connect4.new_board()
        state["turn_id"] = state["p2_id"] if state["turn_id"] == state["p1_id"] else state["p1_id"]
        suffix = "\n\n🤝 Ничья! Новый раунд."
    else:
        state["turn_id"] = state["p2_id"] if cq.from_user.id == state["p1_id"] else state["p1_id"]

    keyboard = connect4.build_keyboard()
    await _end_round_or_finish(cq.inline_message_id, state, "c4", suffix, connect4.build_text, keyboard)


# ---------- напёрстки ----------

@dp.callback_query(F.data.startswith("shell:"))
async def shell_move(cq: CallbackQuery):
    state = storage.get(cq.inline_message_id)
    if not state or state.get("status") != "active" or state["game"] != "shell":
        await cq.answer()
        return
    if cq.from_user.id not in (state["p1_id"], state["p2_id"]):
        await cq.answer("Это не твоя игра 🙂", show_alert=True)
        return
    if cq.from_user.id != state["turn_id"]:
        await cq.answer("Сейчас не твой ход", show_alert=True)
        return

    idx = int(cq.data.split(":")[1])
    sh = state["shell"]
    if idx in sh["revealed_empty"]:
        await cq.answer("Тут уже пусто, попробуй другую", show_alert=True)
        return

    suffix = ""
    if idx == sh["secret"]:
        winner_name = state["p1_name"] if cq.from_user.id == state["p1_id"] else state["p2_name"]
        state["score"][cq.from_user.id] += 1
        await cq.answer("Есть! 🎯")
        suffix = f"\n\n🎉 <b>{winner_name}</b> нашёл(нашла) шарик! Новый раунд."
        finished, _ = _finish_check(state)
        if not finished:
            _init_round(state, "shell")
    else:
        sh["revealed_empty"].add(idx)
        await cq.answer("Пусто 😔")
        state["turn_id"] = state["p2_id"] if cq.from_user.id == state["p1_id"] else state["p1_id"]

    keyboard = shell.build_keyboard(state["shell"])
    await _end_round_or_finish(cq.inline_message_id, state, "shell", suffix, shell.build_text, keyboard)


# ---------- виселица ----------

@dp.callback_query(F.data.startswith("hm:"))
async def hangman_move(cq: CallbackQuery):
    state = storage.get(cq.inline_message_id)
    if not state or state.get("status") != "active" or state["game"] != "hangman":
        await cq.answer()
        return
    if cq.from_user.id not in (state["p1_id"], state["p2_id"]):
        await cq.answer("Это не твоя игра 🙂", show_alert=True)
        return
    if cq.from_user.id != state["turn_id"]:
        await cq.answer("Сейчас не твой ход", show_alert=True)
        return

    letter = cq.data.split(":")[1]
    hm = state["hangman"]
    if letter in hm["guessed"]:
        await cq.answer("Эта буква уже была")
        return
    hm["guessed"].add(letter)

    suffix = ""
    guesser_name = state["p1_name"] if cq.from_user.id == state["p1_id"] else state["p2_name"]

    if letter in hm["word"]:
        await cq.answer("Есть такая буква! ✅")
        if all(ch in hm["guessed"] for ch in hm["word"]):
            state["score"][cq.from_user.id] += 1
            suffix = f"\n\n🎉 Слово «{hm['word']}» отгадано игроком <b>{guesser_name}</b>! Новый раунд."
            finished, _ = _finish_check(state)
            if not finished:
                _init_round(state, "hangman")
        # если слово не отгадано полностью — тот же игрок ходит снова
    else:
        hm["wrong"] += 1
        await cq.answer("Такой буквы нет ❌")
        if hm["wrong"] >= hangman.MAX_WRONG:
            opponent_id = state["p2_id"] if cq.from_user.id == state["p1_id"] else state["p1_id"]
            opponent_name = state["p1_name"] if opponent_id == state["p1_id"] else state["p2_name"]
            state["score"][opponent_id] += 1
            suffix = f"\n\n💀 Слово было «{hm['word']}». Раунд достаётся <b>{opponent_name}</b>! Новый раунд."
            finished, _ = _finish_check(state)
            if not finished:
                _init_round(state, "hangman")
        else:
            state["turn_id"] = state["p2_id"] if cq.from_user.id == state["p1_id"] else state["p1_id"]

    keyboard = hangman.build_keyboard(state["hangman"])
    await _end_round_or_finish(cq.inline_message_id, state, "hangman", suffix, hangman.build_text, keyboard)


# ---------- математическая дуэль ----------

@dp.callback_query(F.data.startswith("math:"))
async def math_move(cq: CallbackQuery):
    state = storage.get(cq.inline_message_id)
    if not state or state.get("status") != "active" or state["game"] != "math":
        await cq.answer()
        return
    if cq.from_user.id not in (state["p1_id"], state["p2_id"]):
        await cq.answer("Это не твоя игра 🙂", show_alert=True)
        return

    idx = int(cq.data.split(":")[1])
    md = state["mathduel"]
    if idx in md["eliminated"]:
        await cq.answer("Этот вариант уже отклонён")
        return

    if md["options"][idx] == md["correct"]:
        winner_name = state["p1_name"] if cq.from_user.id == state["p1_id"] else state["p2_name"]
        state["score"][cq.from_user.id] += 1
        await cq.answer("Верно! ⚡")
        suffix = f"\n\n🎉 <b>{winner_name}</b> ответил(а) первым(ой)! Новый раунд."
        finished, _ = _finish_check(state)
        if not finished:
            _init_round(state, "math")
        keyboard = mathduel.build_keyboard(state["mathduel"])
        await _end_round_or_finish(cq.inline_message_id, state, "math", suffix, mathduel.build_text, keyboard)
    else:
        md["eliminated"].add(idx)
        await cq.answer("Неверно ❌", show_alert=True)
        storage.set(cq.inline_message_id, state)
        await bot.edit_message_text(
            mathduel.build_text(state), inline_message_id=cq.inline_message_id,
            reply_markup=mathduel.build_keyboard(md), parse_mode="HTML",
        )


# ---------- мемори (найди пару) ----------

async def _resolve_memory_mismatch(inline_message_id: str, round_seq: int):
    await asyncio.sleep(1.4)
    state = storage.get(inline_message_id)
    if not state or state.get("status") != "active" or state["game"] != "memory":
        return
    mem = state["memory"]
    if mem.get("round_seq") != round_seq:
        return
    mem["pending"] = []
    mem["locked"] = False
    state["turn_id"] = state["p2_id"] if state["turn_id"] == state["p1_id"] else state["p1_id"]
    storage.set(inline_message_id, state)
    try:
        await bot.edit_message_text(
            memory.build_text(state), inline_message_id=inline_message_id,
            reply_markup=memory.build_keyboard(mem), parse_mode="HTML",
        )
    except Exception:
        pass


@dp.callback_query(F.data.startswith("mem:"))
async def memory_move(cq: CallbackQuery):
    state = storage.get(cq.inline_message_id)
    if not state or state.get("status") != "active" or state["game"] != "memory":
        await cq.answer()
        return
    if cq.from_user.id not in (state["p1_id"], state["p2_id"]):
        await cq.answer("Это не твоя игра 🙂", show_alert=True)
        return
    if cq.from_user.id != state["turn_id"]:
        await cq.answer("Сейчас не твой ход", show_alert=True)
        return

    mem = state["memory"]
    if mem["locked"]:
        await cq.answer("Подожди, идёт проверка пары...")
        return

    idx = int(cq.data.split(":")[1])
    if idx in mem["matched"] or idx in mem["pending"]:
        await cq.answer("Эта карта уже открыта")
        return

    mem["pending"].append(idx)
    await cq.answer()

    if len(mem["pending"]) == 1:
        storage.set(cq.inline_message_id, state)
        await bot.edit_message_text(
            memory.build_text(state), inline_message_id=cq.inline_message_id,
            reply_markup=memory.build_keyboard(mem), parse_mode="HTML",
        )
        return

    i1, i2 = mem["pending"]
    suffix = ""
    if mem["cards"][i1] == mem["cards"][i2]:
        mem["matched"].update(mem["pending"])
        mem["pending"] = []
        mem["pairs"][cq.from_user.id] = mem["pairs"].get(cq.from_user.id, 0) + 1
        suffix = "\n\n🎉 Пара найдена! Ходишь ещё раз."

        if len(mem["matched"]) == memory.SIZE:
            p1_pairs = mem["pairs"].get(state["p1_id"], 0)
            p2_pairs = mem["pairs"].get(state["p2_id"], 0)
            if p1_pairs != p2_pairs:
                winner_id = state["p1_id"] if p1_pairs > p2_pairs else state["p2_id"]
                winner_name = state["p1_name"] if winner_id == state["p1_id"] else state["p2_name"]
                state["score"][winner_id] += 1
                suffix += f"\n\n🏁 Все пары найдены! Раунд выиграл(а) <b>{winner_name}</b>."
            else:
                suffix += "\n\n🏁 Все пары найдены! Ничья в раунде."
            finished, _ = _finish_check(state)
            if not finished:
                _init_round(state, "memory")
        keyboard = memory.build_keyboard(state["memory"])
        await _end_round_or_finish(cq.inline_message_id, state, "memory", suffix, memory.build_text, keyboard)
    else:
        mem["locked"] = True
        mem["round_seq"] = mem.get("round_seq", 0) + 1
        storage.set(cq.inline_message_id, state)
        await bot.edit_message_text(
            memory.build_text(state, "Карты не совпали, запоминай..."),
            inline_message_id=cq.inline_message_id,
            reply_markup=memory.build_keyboard(mem), parse_mode="HTML",
        )
        asyncio.create_task(_resolve_memory_mismatch(cq.inline_message_id, mem["round_seq"]))


# ---------- кто быстрее (reflex) ----------

async def _schedule_reflex_arm(inline_message_id: str, round_seq: int):
    delay = reflex.random_delay()
    await asyncio.sleep(delay)
    state = storage.get(inline_message_id)
    if not state or state.get("status") != "active" or state["game"] != "reflex":
        return
    if state.get("round_seq") != round_seq or state.get("round_resolved"):
        return
    state["armed"] = True
    storage.set(inline_message_id, state)
    try:
        await bot.edit_message_text(
            reflex.build_text_armed(state),
            inline_message_id=inline_message_id,
            reply_markup=reflex.build_keyboard(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@dp.callback_query(F.data == "reflex:press")
async def reflex_press(cq: CallbackQuery):
    state = storage.get(cq.inline_message_id)
    if not state or state.get("status") != "active" or state["game"] != "reflex":
        await cq.answer()
        return
    if cq.from_user.id not in (state["p1_id"], state["p2_id"]):
        await cq.answer("Это не твоя игра 🙂", show_alert=True)
        return
    if state.get("round_resolved"):
        await cq.answer("Раунд уже завершён")
        return

    state["round_resolved"] = True  # блокируем повторную обработку сразу

    opponent_id = state["p2_id"] if cq.from_user.id == state["p1_id"] else state["p1_id"]
    presser_name = state["p1_name"] if cq.from_user.id == state["p1_id"] else state["p2_name"]
    opponent_name = state["p1_name"] if opponent_id == state["p1_id"] else state["p2_name"]

    if state.get("armed"):
        winner_id, winner_name = cq.from_user.id, presser_name
        suffix = f"\n\n⚡ <b>{winner_name}</b> оказался(ась) быстрее!"
        await cq.answer("Ты быстрее! ⚡")
    else:
        winner_id, winner_name = opponent_id, opponent_name
        suffix = f"\n\n🐌 <b>{presser_name}</b> поспешил(а) — раунд достаётся <b>{winner_name}</b>!"
        await cq.answer("Рано! Фальстарт 🐌", show_alert=True)

    state["score"][winner_id] += 1
    storage.set(cq.inline_message_id, state)

    finished, name = _finish_check(state)
    if finished:
        text = f"{reflex.build_text_armed(state) if state.get('armed') else reflex.build_text_waiting(state)}{suffix}\n\n🏆 Победа: <b>{name}</b>! Матч окончен."
        await bot.edit_message_text(text, inline_message_id=cq.inline_message_id, parse_mode="HTML")
        storage.delete(cq.inline_message_id)
        return

    state["round_seq"] += 1
    state["armed"] = False
    state["round_resolved"] = False
    storage.set(cq.inline_message_id, state)
    text = reflex.build_text_waiting(state) + suffix
    await bot.edit_message_text(
        text, inline_message_id=cq.inline_message_id, reply_markup=reflex.build_keyboard(), parse_mode="HTML"
    )
    asyncio.create_task(_schedule_reflex_arm(cq.inline_message_id, state["round_seq"]))


# ---------- запуск через webhook (для Render) ----------

async def on_startup(bot: Bot):
    """
    Устанавливаем webhook с ретраями: на бесплатном Render в первые секунды
    холодного старта сеть иногда отвечает не сразу. Раньше при любом сбое
    здесь падало исключение ДО того, как поднимался HTTP-сервер (web.run_app),
    из-за чего процесс целиком крашился и Render отдавал 502 на все запросы
    (включая /health) — сервис не "спал", а не мог стартовать вообще, поэтому
    пинги от UptimeRobot не помогали.
    """
    url = WEBHOOK_HOST + WEBHOOK_PATH
    attempts = 5
    for attempt in range(1, attempts + 1):
        try:
            await bot.set_webhook(
                url,
                allowed_updates=["message", "inline_query", "chosen_inline_result", "callback_query"],
            )
            log.info("Webhook установлен: %s", url)
            return
        except Exception:
            log.exception(
                "Не удалось установить webhook (попытка %s/%s)", attempt, attempts
            )
            if attempt == attempts:
                # Даже если не получилось — не роняем процесс. Сервер всё равно
                # поднимется и будет отвечать на /health, а вебхук можно
                # переустановить позже (в т.ч. вручную через getWebhookInfo/setWebhook).
                log.error(
                    "Продолжаю запуск без установленного webhook. "
                    "Проверьте BOT_TOKEN и WEBHOOK_URL в переменных окружения Render."
                )
                return
            await asyncio.sleep(min(2 ** attempt, 30))


async def health(request):
    return web.Response(text="ok")


def main():
    dp.startup.register(on_startup)

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
