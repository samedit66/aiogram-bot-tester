# aiogram_bot_tester

> Your missing test toolkit for Telegram bots.

[![CI](https://github.com/samedit66/aiogram-bot-tester/actions/workflows/ci-and-publish.yml/badge.svg?branch=main)](https://github.com/samedit66/aiogram-bot-tester/actions/workflows/ci-and-publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/aiogram-bot-tester?logo=pypi)](https://pypi.org/project/aiogram-bot-tester/)
[![Python 3.10–3.15](https://img.shields.io/badge/Python-3.10%E2%80%933.15-blue?logo=python)](https://github.com/samedit66/aiogram-bot-tester/actions/workflows/ci-and-publish.yml)
[![aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-blue?logo=telegram)](https://docs.aiogram.dev/)
[![Apache 2.0 license](https://img.shields.io/badge/license-Apache%202.0-blue)](https://github.com/samedit66/aiogram-bot-tester/blob/main/LICENSE)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/aiogram-bot-tester?period=total&units=INTERNATIONAL_SYSTEM&left_color=GRAY&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/aiogram-bot-tester)

> [!WARNING]
> This library is under active development. Its API is unstable and may contain
> frequent breaking changes between releases.

- [English tutorial](https://github.com/samedit66/aiogram-bot-tester/blob/main/docs/TUTORIAL_EN.MD)
- [Русский туториал](https://github.com/samedit66/aiogram-bot-tester/blob/main/docs/TUTORIAL_RU.md)

## Installation

Stable version:

```bash
pip install aiogram_bot_tester
```

Latest development version:

```bash
pip install git+https://github.com/samedit66/aiogram-bot-tester.git
```

## What's that?

`aiogram_bot_tester` is a lightweight way to test aiogram bots offline, without real Telegram API calls. It helps you simulate updates, check bot responses, and keep tests deterministic, so bot logic can be covered with confidence even when the conversation flow is complex.

## Features

- **Fully offline testing** — run bot scenarios without a Telegram token, network requests, or real API calls.
- **Real aiogram pipeline** — updates pass through the actual dispatcher, routers, filters, middleware, and FSM machinery.
- **Conversation-first API** — send messages and commands, start the bot, and tap reply or callback buttons by their visible labels.
- **Readable assertions** — check message text, regular expressions, buttons, callback data, URLs, and complete keyboard layouts.
- **FSM support** — assert the current state and inspect FSM data across multi-step conversation flows.
- **Flexible test setup** — build a tester from reusable routers or an existing dispatcher, pass fake dependencies directly, and attach middleware when needed.

## Quick example

Install `pytest` and `pytest-asyncio` in your test environment to run this example.

```python
from datetime import datetime, timezone

import pytest
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PhotoSize,
    Update,
    User,
)

from aiogram_bot_tester import BotTester

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Hello! Press Continue or send me your name.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Continue", callback_data="continue")]
            ]
        ),
    )


@router.message(F.text)
async def echo_name(message: Message) -> None:
    await message.answer(f"Nice to meet you, {message.text}!")


@router.message(F.photo)
async def receive_photo(message: Message) -> None:
    await message.answer("Photo received.")


@router.callback_query(F.data == "continue")
async def on_continue(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.answer("Please send your name.")


@pytest.mark.asyncio
async def test_flow() -> None:
    tester = BotTester.from_routers(router)

    response = await tester.start()
    response.assert_contains("Hello")
    response.assert_button("Continue")

    response = await tester.tap_button("Continue")
    response.assert_contains("Please send your name.")

    response = await tester.send_message("Bob")
    response.assert_contains("Nice to meet you, Bob!")

    update = Update(
        update_id=100,
        message=Message(
            message_id=100,
            date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            chat=Chat(id=1, type="private"),
            from_user=User(id=1, is_bot=False, first_name="Bob"),
            photo=[PhotoSize(file_id="photo", file_unique_id="unique", width=64, height=64)],
        ),
    )
    (response,) = await tester.feed_update(update)
    response.assert_contains("Photo received.")
```

## Custom updates and API calls

Pass an aiogram `Update` to `await tester.feed_update(update)` to test photo messages, inline queries, and other events handled by your dispatcher. The method returns a tuple of captured messages and edits in order. It returns an empty tuple when the handler produces no captured message.

Use `tester.api_calls` to inspect outgoing aiogram methods in call order. For example, after handling an inline query, check that the bot called `AnswerInlineQuery`.

`SendMessage` returns an aiogram `Message` that can be edited with `edit_text()` and `edit_reply_markup()`. Sending text and editing a chat message both produce a `BotMessage` for assertions. `AnswerCallbackQuery` returns `True` and only appears in the call history. Other unsupported methods return mocks and can be asserted through the same history.
