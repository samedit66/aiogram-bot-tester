# aiogram_bot_tester

![aiogram](https://img.shields.io/badge/aiogram-3.x-blue?logo=telegram)
![telegram](https://img.shields.io/badge/telegram-bot-blue?logo=telegram)
![status](https://img.shields.io/badge/status-WIP-orange)
![python](https://img.shields.io/badge/python-3.10+-blue?logo=python)

A lightweight testing utility for **offline testing of aiogram bots without real Telegram API calls**.

Its goal is to make it easy to test bot logic deterministically by simulating Telegram updates, intercepting bot API calls, and exposing a clean assertion-friendly response layer.

---

# Installation

With pip:

```bash
pip install git+https://github.com/samedit66/aiogram-bot-tester.git
```

With poetry:

```bash
poetry add git+https://github.com/samedit66/aiogram-bot-tester.git
```

With uv:

```bash
uv add git+https://github.com/samedit66/aiogram-bot-tester.git
```

---

# What is this?

`aiogram_bot_tester` is a testing framework for bots built with `aiogram`.

Instead of running a real Telegram bot, it:

- simulates incoming Telegram updates (`Message`, `CallbackQuery`)
- intercepts outgoing bot API calls (`send_message`, etc.)
- captures state changes (`FSM`)
- provides a clean assertion API

### Goal

Enable fast, deterministic, offline testing of Telegram bots without network, tokens, or Telegram API dependency.

---

# Quick example

```python
tester = BotTester.from_routers(router)

response = await tester.send_message("/start")

assert response.text == "Hello"
assert response.has_inline_button("Press")
```

---

# Core API

## BotTester.from_routers(*routers)

Construct a `BotTester` instance from a sequence of `Routers`s.

```python
tester = BotTester.from_routers(router)
```

## send_message(text, **kwargs)

Send a message to the bot. Returns a special `Response` object described below.

```python
response = await tester.send_message("/start")
assert response.text == "Hello"
```

## click_reply_button(text, **kwargs)

Simulates clicking a reply button. Actually, it's just another way of calling `send_message`. Exists just to clarify intention.

```python
response = await tester.click_reply_button("Option A")
```

## click_inline_button(label)

Simulates clicking an inline button.

```python
response = await tester.click_inline_button("Press")
```

---

# Response object

Each interaction with a `BotTester` returns a `Response` object.

```python
@dataclass
class Response:
    text: str | None
    state: State | None
    message: object | None
```

## Response.text

Last bot message text.

## Response.state

FSM state.

Example:

```python
class Form(StatesGroup):
    name = State()
    surname = State()
    age = State()

# Inside a test:

response = await tester.send_message("/start")
assert response.state == Form.name # in_state() method does the same
```

## Response.contains(substring)

Returns `True` if this response text contains the given `substring`, `False` otherwise.

Example:

```python
assert response.contains("Hello")
```

## Response.matches(regex)

Returns `True` if this response text matches the given `regex`, `False` otherwise.

Example:

```python
assert response.matches("\d+")
```

## Response.has_inline_button(label)

Returns `True` if this response has an inline button with `label`, `False` otherwise.

Example:

```python
assert response.has_inline_button("Click me!")
```

## Response.has_reply_button(label)

Returns `True` if this response has a button with `label`, `False` otherwise.

Example:

```python
assert response.has_reply_button("Click me!")
```

## Response.has_inline_keyboard_like(keyboard)

Returns `True` if this response has the specified inline `keyboard`, `False` otherwise.

Example:

```python
assert response.has_inline_keyboard_like([
    ["Yes", "No"],
    ["Cancel"],
])
```

## Response.has_reply_keyboard_like(keyboard)

Returns `True` if this response has the specified reply `keyboard`, `False` otherwise.

Example:

```python
assert response.has_reply_keyboard_like([
    ["1", "2", "3"],
    ["4", "5", "6"],
])
```

---

# 🚀 Full example

```python
import pytest
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from aiogram_bot_tester import BotTester

router = Router()

@router.message()
async def echo(message: Message):
    await message.answer(
        f"Echo: {message.text}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Press me", callback_data="press")]
            ]
        ),
    )

@router.callback_query(F.data == "press")
async def on_press(callback: CallbackQuery):
    await callback.message.answer("Button clicked!")

@pytest.mark.asyncio
async def test_full_flow():
    tester = BotTester.from_routers(router)

    response = await tester.send_message("Hello")
    assert response.text == "Echo: Hello"

    response = await tester.click_inline_button("Press me")
    assert response.text == "Button clicked!"
```
