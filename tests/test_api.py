import pytest
from aiogram import F, Router
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

from aiogram_bot_tester import BotTester

# ============================================================
# BASIC MESSAGE FLOW
# ============================================================


@pytest.mark.asyncio
async def test_send_message_returns_response():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer("Hello")

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.text == "Hello"
    assert response.contains("ll")
    assert response.matches("[hH]ello")


@pytest.mark.asyncio
async def test_send_message_without_response():
    router = Router()

    @router.message()
    async def handler(message: Message):
        pass

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.text is None


# ============================================================
# REPLY KEYBOARDS
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

    assert response.has_reply_button("A")
    assert not response.has_reply_button("B")


@pytest.mark.asyncio
async def test_has_reply_keyboard_like():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer(
            "Choose",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [
                        KeyboardButton(text="1"),
                        KeyboardButton(text="2"),
                    ],
                    [
                        KeyboardButton(text="3"),
                    ],
                ],
                resize_keyboard=True,
            ),
        )

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.has_reply_keyboard_like(
        [
            ["1", "2"],
            ["3"],
        ]
    )


# ============================================================
# INLINE KEYBOARDS
# ============================================================


@pytest.mark.asyncio
async def test_has_inline_button():
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

    assert response.has_inline_button("Press")
    assert not response.has_inline_button("Missing")


@pytest.mark.asyncio
async def test_has_inline_keyboard_like():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer(
            "Choose",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="1", callback_data="1"),
                        InlineKeyboardButton(text="2", callback_data="2"),
                    ],
                    [
                        InlineKeyboardButton(text="3", callback_data="3"),
                    ],
                ]
            ),
        )

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.has_inline_keyboard_like(
        [
            ["1", "2"],
            ["3"],
        ]
    )


# ============================================================
# CALLBACK FLOW (INLINE BUTTON CLICK)
# ============================================================


@pytest.mark.asyncio
async def test_click_inline_button_triggers_callback():
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

    response = await tester.click_inline_button("Press")

    assert response.text == "Clicked"


# ============================================================
# FSM STATE HANDLING
# ============================================================


class Form(StatesGroup):
    main = State()


@pytest.mark.asyncio
async def test_fsm_state_is_captured():
    router = Router()

    @router.message()
    async def handler(
        message: Message,
        state: FSMContext,
    ):
        await state.set_state(Form.main)
        await message.answer("Hello")

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.state == Form.main


# ============================================================
# MESSAGE HISTORY
# ============================================================


@pytest.mark.asyncio
async def test_message_history_is_stored():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer("First")
        await message.answer("Second")

    tester = BotTester.from_routers(router)

    response = await tester.send_message("/start")

    assert response.text == "Second"

    assert len(tester.messages) == 2
    assert tester.messages[0].text == "First"
    assert tester.messages[1].text == "Second"


# ============================================================
# ERROR CASES
# ============================================================


@pytest.mark.asyncio
async def test_clicking_missing_inline_button_raises():
    router = Router()

    tester = BotTester.from_routers(router)

    with pytest.raises(ValueError):
        await tester.click_inline_button("Missing")


@pytest.mark.asyncio
async def test_inline_button_without_callback_data_raises():
    router = Router()

    @router.message()
    async def handler(message: Message):
        await message.answer(
            "Choose",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Broken",
                            callback_data=None,
                        )
                    ]
                ]
            ),
        )

    tester = BotTester.from_routers(router)

    await tester.send_message("/start")

    with pytest.raises(ValueError):
        await tester.click_inline_button("Broken")
