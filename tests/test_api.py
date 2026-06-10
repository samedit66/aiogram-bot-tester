import pytest
from aiogram import F, Router
from aiogram.filters.command import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from aiogram_bot_tester.bot_tester import (
    BotTester,
    ButtonNotFoundError,
    NoBotMessageError,
    NoBotResponseError,
)

# ============================================================
# SEND MESSAGE
# ============================================================


@pytest.mark.asyncio
async def test_send_message():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer("Hello")

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.text == "Hello"


@pytest.mark.asyncio
async def test_send_message_no_response():
    router = Router()

    @router.message()
    async def handler(message: Message):
        pass

    tester = BotTester.from_routers(router)

    with pytest.raises(NoBotResponseError):
        await tester.send_message("/start")


@pytest.mark.asyncio
async def test_send_message_contains_text():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer("Hello World")

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.contains_text("Hello")
    assert response.contains_text("World")
    assert not response.contains_text("Goodbye")


@pytest.mark.asyncio
async def test_send_message_search_regex():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer("Order #123")

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.search_regex(r"\d+")
    assert response.search_regex(r"Order")
    assert not response.search_regex(r"Goodbye")


# ============================================================
# SEND COMMAND
# ============================================================


@pytest.mark.asyncio
async def test_send_command():
    router = Router()

    @router.message(Command("sum"))
    async def cmd_sum(
        message: Message,
        command: CommandObject,
    ):
        a, b = map(int, command.args.split())
        await message.answer(str(a + b))

    tester = BotTester.from_routers(router)

    response = await tester.send_command("sum", 1, 2)

    assert response.text == "3"


@pytest.mark.asyncio
async def test_start():
    router = Router()

    @router.message(Command("start"))
    async def start_handler(message: Message):
        await message.answer("Welcome")

    tester = BotTester.from_routers(router)

    response = await tester.start()

    assert response.text == "Welcome"


# ============================================================
# BUTTON ASSERTIONS
# ============================================================


@pytest.mark.asyncio
async def test_has_reply_button():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer(
            "Choose",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="A")],
                ],
                resize_keyboard=True,
            ),
        )

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.has_button("A")
    assert not response.has_button("B")


@pytest.mark.asyncio
async def test_has_callback_button():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer(
            "Choose",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Press",
                            callback_data="press",
                        )
                    ]
                ]
            ),
        )

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.has_callback_button(
        "Press",
        callback_data="press",
    )

    assert not response.has_callback_button(
        "Press",
        callback_data="wrong",
    )


@pytest.mark.asyncio
async def test_has_url_button():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer(
            "Links",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Google",
                            url="https://google.com",
                        )
                    ]
                ]
            ),
        )

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.has_url_button(
        "Google",
        "https://google.com",
    )


@pytest.mark.asyncio
async def test_has_keyboard():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer(
            "Choose",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="1",
                            callback_data="1",
                        ),
                        InlineKeyboardButton(
                            text="2",
                            callback_data="2",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="3",
                            callback_data="3",
                        )
                    ],
                ]
            ),
        )

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.has_keyboard(
        [
            ["1", "2"],
            ["3"],
        ]
    )


# ============================================================
# TAP BUTTON
# ============================================================


@pytest.mark.asyncio
async def test_tap_reply_button():
    router = Router()

    @router.message(F.text == "/start")
    async def start_handler(message: Message):
        await message.answer(
            "Choose",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Next")]],
                resize_keyboard=True,
            ),
        )

    @router.message(F.text == "Next")
    async def next_handler(message: Message):
        await message.answer("Done")

    tester = BotTester.from_routers(router)

    await tester.send_message("/start")

    response = await tester.tap_button("Next")

    assert response.text == "Done"


@pytest.mark.asyncio
async def test_tap_callback_button():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer(
            "Choose",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Press",
                            callback_data="press",
                        )
                    ]
                ]
            ),
        )

    @router.callback_query(F.data == "press")
    async def callback_handler(callback: CallbackQuery):
        await callback.message.answer("Clicked")

    tester = BotTester.from_routers(router)

    await tester.send_message("/start")

    response = await tester.tap_button("Press")

    assert response.text == "Clicked"


# ============================================================
# FSM
# ============================================================


class Form(StatesGroup):
    main = State()


@pytest.mark.asyncio
async def test_in_state():
    router = Router()

    @router.message()
    async def handler(
        message: Message,
        state: FSMContext,
    ):
        await state.set_state(Form.main)
        await message.answer("Hello")

    tester = BotTester.from_routers(router)

    await tester.send_message("/start")

    assert await tester.in_state(Form.main)
    assert not await tester.in_state(None)


@pytest.mark.asyncio
async def test_data_has():
    router = Router()

    @router.message()
    async def handler(
        message: Message,
        state: FSMContext,
    ):
        await state.update_data(name="Bob")
        await message.answer("Hello")

    tester = BotTester.from_routers(router)

    await tester.send_message("/start")

    assert await tester.data_has(name="Bob")
    assert not await tester.data_has(name="Alice")


# ============================================================
# ERRORS
# ============================================================


@pytest.mark.asyncio
async def test_tap_button_without_last_message():
    tester = BotTester.from_routers(Router())

    with pytest.raises(NoBotMessageError):
        await tester.tap_button("Anything")


@pytest.mark.asyncio
async def test_tap_missing_button():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer("Hello")

    tester = BotTester.from_routers(router)

    await tester.send_message("/start")

    with pytest.raises(ButtonNotFoundError):
        await tester.tap_button("Missing")


@pytest.mark.asyncio
async def test_tap_button_without_response():
    router = Router()

    @router.message(F.text == "/start")
    async def start_handler(message: Message):
        await message.answer(
            "Choose",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Next")]],
                resize_keyboard=True,
            ),
        )

    @router.message(F.text == "Next")
    async def next_handler(message: Message):
        pass

    tester = BotTester.from_routers(router)

    await tester.send_message("/start")

    with pytest.raises(NoBotResponseError):
        await tester.tap_button("Next")
