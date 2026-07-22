import pytest
from aiogram import F, Router
from aiogram.dispatcher.middlewares.base import BaseMiddleware
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

from aiogram_bot_tester.bot_tester import BotTester
from aiogram_bot_tester.exceptions import (
    ButtonNotFoundError,
    InvalidTranscriptError,
    NoBotMessageError,
    NoBotResponseError,
)


class RecordingMiddleware(BaseMiddleware):
    def __init__(self, name, calls):
        self.name = name
        self.calls = calls

    async def __call__(self, handler, event, data):
        self.calls.append((self.name, type(event).__name__))
        data["middleware_names"] = [
            *data.get("middleware_names", []),
            self.name,
        ]
        return await handler(event, data)


# ============================================================
# SEND MESSAGE
# ============================================================


@pytest.mark.asyncio
async def test_from_routers_registers_middlewares_in_order():
    router = Router()
    calls = []

    @router.message()
    async def handler(message: Message, middleware_names: list[str]):
        await message.answer(",".join(middleware_names))

    tester = BotTester.from_routers(
        router,
        middlewares=[
            RecordingMiddleware("first", calls),
            RecordingMiddleware("second", calls),
        ],
    )

    response = await tester.send_message("/start")

    assert response.text == "first,second"
    assert calls == [("first", "Message"), ("second", "Message")]


@pytest.mark.asyncio
async def test_from_routers_registers_middlewares_for_callback_queries():
    router = Router()
    calls = []

    @router.message()
    async def message_handler(message: Message):
        await message.answer(
            "Choose",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Press", callback_data="press")]
                ]
            ),
        )

    @router.callback_query(F.data == "press")
    async def callback_handler(
        callback: CallbackQuery,
        middleware_names: list[str],
    ):
        await callback.message.answer(",".join(middleware_names))

    tester = BotTester.from_routers(
        router,
        middlewares=[RecordingMiddleware("tracked", calls)],
    )

    await tester.send_message("/start")
    response = await tester.tap_button("Press")

    assert response.text == "tracked"
    assert calls == [("tracked", "Message"), ("tracked", "CallbackQuery")]


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
async def test_send_message_contains():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer("Hello World")

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.contains("Hello")
    assert response.contains("Goodbye", "World")
    assert not response.contains("Goodbye", "Farewell")


@pytest.mark.asyncio
async def test_send_message_matches():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer("Order #123")

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.matches(r"\d+")
    assert response.matches(r"Goodbye", r"Order")
    assert not response.matches(r"Goodbye", r"Hello")


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
        url="https://google.com",
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


# ============================================================
# DECLARATIVE CHAT TESTING
# ============================================================


@pytest.mark.asyncio
async def test_chat_simple_flow():
    router = Router()

    @router.message(Command("start"))
    async def start_handler(message: Message):
        await message.answer("Hello! What's your name?")

    @router.message(F.text == "Bob")
    async def name_handler(message: Message):
        await message.answer("Hi, Bob!")

    tester = BotTester.from_routers(router)

    await tester.chat(
        """
        User: /start
        Bot: Hello! What's your name?

        User: Bob
        Bot: Hi, Bob!
        """
    )


@pytest.mark.asyncio
async def test_chat_multiline_bot_response():
    router = Router()

    @router.message(Command("start"))
    async def start_handler(message: Message):
        await message.answer("Welcome to the bot!\nPlease choose an option.")

    tester = BotTester.from_routers(router)

    await tester.chat(
        """
        User: /start
        Bot: Welcome to the bot!
        """
    )


@pytest.mark.asyncio
async def test_chat_bot_text_mismatch():
    router = Router()

    @router.message(Command("start"))
    async def start_handler(message: Message):
        await message.answer("Hello!")

    tester = BotTester.from_routers(router)

    with pytest.raises(AssertionError):
        await tester.chat(
            """
            User: /start
            Bot: Goodbye!
            """
        )


@pytest.mark.asyncio
async def test_chat_no_bot_response():
    router = Router()

    @router.message(Command("start"))
    async def start_handler(message: Message):
        pass  # bot doesn't respond

    tester = BotTester.from_routers(router)

    with pytest.raises(NoBotResponseError):
        await tester.chat(
            """
            User: /start
            Bot: Hello!
            """
        )


@pytest.mark.asyncio
async def test_chat_malformed_transcript_wrong_format():
    router = Router()
    tester = BotTester.from_routers(router)

    with pytest.raises(InvalidTranscriptError):
        await tester.chat(
            """
            User: /start

            Wrong format here
            """
        )


@pytest.mark.asyncio
async def test_chat_malformed_transcript_missing_user_prefix():
    router = Router()
    tester = BotTester.from_routers(router)

    with pytest.raises(InvalidTranscriptError):
        await tester.chat(
            """
            Message: /start
            Bot: Hello!
            """
        )


@pytest.mark.asyncio
async def test_chat_malformed_transcript_missing_bot_prefix():
    router = Router()
    tester = BotTester.from_routers(router)

    with pytest.raises(InvalidTranscriptError):
        await tester.chat(
            """
            User: /start
            Message: Hello!
            """
        )


@pytest.mark.asyncio
async def test_chat_multiple_turns():
    router = Router()

    @router.message(Command("start"))
    async def start_handler(message: Message):
        await message.answer("What's your name?")

    @router.message(F.text == "Alice")
    async def name_handler(message: Message):
        await message.answer("Hello, Alice!")

    @router.message(F.text == "25")
    async def age_handler(message: Message):
        await message.answer("Thanks for the info!")

    tester = BotTester.from_routers(router)

    await tester.chat(
        """
        User: /start
        Bot: What's your name?

        User: Alice
        Bot: Hello, Alice!

        User: 25
        Bot: Thanks for the info!
        """
    )


@pytest.mark.asyncio
async def test_chat_bot_response_contains_expected():
    router = Router()

    @router.message(Command("start"))
    async def start_handler(message: Message):
        await message.answer(
            "Hello, user! Welcome to our service. How can I help you today?"
        )

    tester = BotTester.from_routers(router)

    # Substring match should pass even though full text differs
    await tester.chat(
        """
        User: /start
        Bot: Welcome to our service
        """
    )
