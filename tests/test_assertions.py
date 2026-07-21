import re

import pytest
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from aiogram_bot_tester import BotMessage, BotTester
from aiogram_bot_tester.types import Button, CallbackButton, UrlButton


def test_contains_uses_any_semantics() -> None:
    response = BotMessage("Hello World", [])

    assert response.contains("Hello")
    assert response.contains("Goodbye", "World")
    assert not response.contains("Goodbye", "Farewell")


def test_contains_handles_message_without_text() -> None:
    response = BotMessage(None, [])

    assert not response.contains("Hello")


def test_contains_handles_empty_text_and_empty_fragment() -> None:
    response = BotMessage("", [])

    assert response.contains("")
    with pytest.raises(
        AssertionError,
        match=re.escape("Expected message not to contain '', but found ('',) in ''."),
    ):
        response.refute_contains("")


def test_assert_and_refute_contains() -> None:
    response = BotMessage("Hello World", [])

    response.assert_contains("Goodbye", "World")
    response.refute_contains("Error", "Failure")

    with pytest.raises(
        AssertionError,
        match=re.escape(
            "Expected message to contain any of ('Goodbye', 'Farewell'), "
            "but got 'Hello World'."
        ),
    ):
        response.assert_contains("Goodbye", "Farewell")

    with pytest.raises(
        AssertionError,
        match=re.escape(
            "Expected message not to contain any of ('Hello', 'World'), "
            "but found ('Hello', 'World') in 'Hello World'."
        ),
    ):
        response.refute_contains("Hello", "World")


def test_single_contains_assertion_has_concise_error() -> None:
    response = BotMessage("Goodbye", [])

    with pytest.raises(
        AssertionError,
        match=re.escape("Expected message to contain 'Hello', but got 'Goodbye'."),
    ):
        response.assert_contains("Hello")


def test_matches_uses_any_semantics_and_accepts_compiled_patterns() -> None:
    response = BotMessage("Order #123", [])

    assert response.matches(r"Order #\d+")
    assert response.matches(r"Goodbye", re.compile(r"#\d+"))
    assert not response.matches(r"Goodbye", re.compile(r"#abc"))


def test_matches_handles_message_without_text() -> None:
    response = BotMessage(None, [])

    assert not response.matches(r".+")


def test_assert_and_refute_matches() -> None:
    response = BotMessage("Order #123", [])

    response.assert_matches(r"Goodbye", r"#\d+")
    response.refute_matches(r"Traceback", r"Exception")

    with pytest.raises(
        AssertionError,
        match=re.escape(
            "Expected message to match any of ('Goodbye', '#abc'), "
            "but got 'Order #123'."
        ),
    ):
        response.assert_matches(r"Goodbye", r"#abc")

    with pytest.raises(AssertionError) as exc_info:
        response.refute_matches(r"Order", r"#\d+")

    assert str(exc_info.value) == (
        "Expected message not to match any of ('Order', '#\\\\d+'), "
        "but these patterns matched: ('Order', '#\\\\d+'). "
        "Actual text: 'Order #123'."
    )


def test_single_regex_assertion_has_concise_error() -> None:
    response = BotMessage("No orders", [])

    with pytest.raises(AssertionError) as exc_info:
        response.assert_matches(r"Order #\d+")

    assert str(exc_info.value) == (
        "Expected message to match 'Order #\\\\d+', but got 'No orders'."
    )


def test_button_assertions() -> None:
    response = BotMessage(
        "Choose",
        [
            [Button("Back")],
            [CallbackButton("Continue", "continue")],
            [UrlButton("Docs", "https://example.com/docs")],
        ],
    )

    response.assert_button("Back")
    response.refute_button("Cancel")
    response.assert_callback_button("Continue", callback_data="continue")
    response.refute_callback_button("Delete", callback_data="delete")
    response.assert_url_button("Docs", url="https://example.com/docs")
    response.refute_url_button("Legacy", url="https://old.example.com")

    with pytest.raises(
        AssertionError,
        match=re.escape(
            "Expected message to have button 'Cancel', but available buttons were "
            "['Back', 'Continue', 'Docs']."
        ),
    ):
        response.assert_button("Cancel")

    with pytest.raises(AssertionError, match="but it was present"):
        response.refute_button("Back")

    with pytest.raises(
        AssertionError,
        match=re.escape(
            "but available callback buttons were [('Continue', 'continue')]."
        ),
    ):
        response.assert_callback_button("Continue", callback_data="next")

    with pytest.raises(AssertionError, match="but it was present"):
        response.refute_callback_button("Continue", callback_data="continue")

    with pytest.raises(
        AssertionError,
        match=re.escape(
            "but available URL buttons were [('Docs', 'https://example.com/docs')]."
        ),
    ):
        response.assert_url_button("Docs", url="https://old.example.com")

    with pytest.raises(AssertionError, match="but it was present"):
        response.refute_url_button("Docs", url="https://example.com/docs")


def test_keyboard_assertions() -> None:
    response = BotMessage("Choose", [[Button("Yes"), Button("No")]])

    response.assert_keyboard([["Yes", "No"]])
    response.refute_keyboard([["No", "Yes"]])

    with pytest.raises(
        AssertionError,
        match=re.escape("Expected keyboard [['Yes']], but got [['Yes', 'No']]."),
    ):
        response.assert_keyboard([["Yes"]])

    with pytest.raises(
        AssertionError,
        match=re.escape(
            "Expected keyboard not to equal [['Yes', 'No']], but it matched exactly."
        ),
    ):
        response.refute_keyboard([["Yes", "No"]])


class Form(StatesGroup):
    main = State()


@pytest.mark.asyncio
async def test_state_and_data_assertions() -> None:
    router = Router()

    @router.message()
    async def handler(message: Message, state: FSMContext) -> None:
        await state.set_state(Form.main)
        await state.update_data(name="Bob", age=30)
        await message.answer("Hello")

    tester = BotTester.from_routers(router)
    await tester.send_message("/start")

    await tester.assert_state(Form.main)
    await tester.refute_state(None)
    await tester.assert_data(name="Bob")
    await tester.refute_data(name="Alice")

    with pytest.raises(AssertionError, match="Expected bot state to be None"):
        await tester.assert_state(None)

    with pytest.raises(AssertionError, match="but it was active"):
        await tester.refute_state(Form.main)

    with pytest.raises(
        AssertionError,
        match=re.escape(
            "Expected FSM data to contain {'name': 'Alice'}, "
            "but current data was {'name': 'Bob', 'age': 30}."
        ),
    ):
        await tester.assert_data(name="Alice")

    with pytest.raises(
        AssertionError,
        match=re.escape(
            "Expected FSM data not to contain {'name': 'Bob'}, "
            "but all specified values were present in {'name': 'Bob', 'age': 30}."
        ),
    ):
        await tester.refute_data(name="Bob")
