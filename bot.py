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
from games import tictactoe, rps, dice

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gamebot")

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_HOST = os.environ["WEBHOOK_URL"].rstrip("/")  # напр. https://your-app.onrender.com
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
PORT = int(os.environ.get("PORT", 10000))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------- /start ----------

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🎮 Я бот для мини-игр между двумя игроками.\n\n"
        "Чтобы вызвать друга, напиши в любом чате:\n"
        f"<code>@{(await bot.me()).username} username_друга</code>\n\n"
        "Появится список игр — выбери одну, друг примет вызов кнопкой "
        "и начнётся матч до 3 побед!",
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


# ---------- фиксируем, кто и кого вызвал (нужно inline_message_id) ----------

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

    if code == "ttt":
        state["board"] = tictactoe.new_board()
        state["turn_id"] = state["p1_id"]
        text, keyboard = tictactoe.build_text(state), tictactoe.build_keyboard(state["board"])
    elif code == "rps":
        state["round_picks"] = {}
        text, keyboard = rps.build_text(state), rps.build_keyboard()
    else:
        state["round_rolls"] = {}
        text, keyboard = dice.build_text(state), dice.build_keyboard()

    storage.set(inline_message_id, state)
    await bot.edit_message_text(text, inline_message_id=inline_message_id, reply_markup=keyboard, parse_mode="HTML")
    await cq.answer()


def _finish_check(state: dict) -> tuple[bool, str | None]:
    for pid, score in state["score"].items():
        if score >= WIN_SCORE:
            name = state["p1_name"] if pid == state["p1_id"] else state["p2_name"]
            return True, name
    return False, None


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

    finished, name = _finish_check(state)
    storage.set(cq.inline_message_id, state)
    await cq.answer()

    if finished:
        text = f"{tictactoe.build_text(state)}{suffix}\n\n🏆 Победа: <b>{name}</b>! Матч окончен."
        await bot.edit_message_text(text, inline_message_id=cq.inline_message_id, parse_mode="HTML")
        storage.delete(cq.inline_message_id)
    else:
        text = tictactoe.build_text(state) + suffix
        keyboard = tictactoe.build_keyboard(state["board"])
        await bot.edit_message_text(text, inline_message_id=cq.inline_message_id, reply_markup=keyboard, parse_mode="HTML")


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


# ---------- запуск через webhook (для Render) ----------

async def on_startup(bot: Bot):
    await bot.set_webhook(
        WEBHOOK_HOST + WEBHOOK_PATH,
        allowed_updates=["message", "inline_query", "chosen_inline_result", "callback_query"],
    )
    log.info("Webhook установлен: %s", WEBHOOK_HOST + WEBHOOK_PATH)


async def health(request):
    return web.Response(text="ok")


def main():
    dp.startup.register(on_startup)

    app = web.Application()
    app.router.add_get("/health", health)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
