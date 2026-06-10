import asyncio
import os

import aiogram
import pytest
from aiogram import filters, types
from aiogram.fsm import context, state

from aiogram_bot_tester import BotTester

# ============================================================
# SETUP THE BOT TO TEST.
# ============================================================


class Registration(state.StatesGroup):
    name = state.State()
    password = state.State()


router = aiogram.Router()


@router.message(filters.CommandStart())
async def cmd_start(
    message: types.Message,
    state: context.FSMContext,
) -> None:
    await message.answer("Hello! What's your name?")
    await state.set_state(Registration.name)


@router.message(Registration.name, aiogram.F.text)
async def name_chosen(
    message: types.Message,
    state: context.FSMContext,
) -> None:
    name = message.text

    await message.answer(f"Hi, {name}! I like your name. What about your password?")

    await state.update_data(name=name)
    await state.set_state(Registration.password)


@router.message(Registration.password, aiogram.F.text)
async def password_chosen(
    message: types.Message,
    state: context.FSMContext,
) -> None:
    password = message.text

    await message.answer("Good, a strong one! Thank you!")

    await state.update_data(password=password)

    # Let's pretend here we did something clever
    # with credentials, right?

    await state.clear()


@router.message(lambda _message: True)
async def fallback(message: types.Message) -> None:
    await message.reply("I don't quite understand you...")


async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    bot = aiogram.Bot(token=token)

    dp = aiogram.Dispatcher()
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


# ============================================================
# TESTS
# ============================================================


@pytest.fixture
def tester() -> BotTester:
    return BotTester.from_routers(router)


@pytest.mark.asyncio
async def test_full_registration(
    tester: BotTester,
) -> None:
    response = await tester.start()

    assert response.contains_text("Hello! What's your name?")

    assert await tester.in_state(Registration.name)

    response = await tester.send_message("Bob")

    assert response.contains_text(
        "Hi, Bob! I like your name. What about your password?"
    )

    assert await tester.in_state(Registration.password)

    assert await tester.data_has(name="Bob")

    response = await tester.send_message("qwerty123")

    assert response.contains_text("Good, a strong one! Thank you!")

    assert await tester.in_state(None)


@pytest.mark.asyncio
async def test_fallback(
    tester: BotTester,
) -> None:
    response = await tester.send_message("/hehe")

    assert response.contains_text("I don't quite understand you...")
