# aiogram_bot_tester

![aiogram](https://img.shields.io/badge/aiogram-3.x-blue?logo=telegram)
![telegram](https://img.shields.io/badge/telegram-bot-blue?logo=telegram)
![status](https://img.shields.io/badge/status-WIP-orange)
![python](https://img.shields.io/badge/python-3.10+-blue?logo=python)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/aiogram-bot-tester?period=total&units=INTERNATIONAL_SYSTEM&left_color=GRAY&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/aiogram-bot-tester)

> [!WARNING]
> This library is under active development. Its API is unstable and may contain
> frequent breaking changes between releases.

- [English tutorial](docs/TUTORIAL_EN.MD)
- [Русский туториал](docs/TUTORIAL_RU.md)

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

## Quick example

```python
import pytest
import aiogram
from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from aiogram_bot_tester import BotTester

router = aiogram.Router()


@router.message(aiogram.filters.CommandStart())
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


@router.callback_query(F.data == "continue")
async def on_continue(callback: CallbackQuery) -> None:
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
```
