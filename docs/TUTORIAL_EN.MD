# aiogram-bot-tester Tutorial

## Introduction

Testing is one of the most important parts of software development. Telegram bots are no exception. A well-designed test suite gives confidence that new features do not break existing functionality and allows teams to iterate faster.

In an ideal architecture, a Telegram bot contains very little logic inside handlers. Handlers should only receive updates, call business services, and return responses. The actual business logic should live in a separate package that can be unit tested independently.

However, reality is often different.

Many Telegram bots evolve quickly, and significant parts of their logic end up inside handlers, FSM flows, callback handlers, and router chains. While separating everything into services may be architecturally cleaner, doing so too early can become unnecessary overengineering and delay the release of the actual product.

This is exactly the problem **aiogram-bot-tester** addresses.

Instead of focusing on testing individual handlers in isolation, the library allows you to test **the entire conversational flow** of your bot in an offline and deterministic way.

## What Makes aiogram-bot-tester Different?

Many testing libraries for Telegram bots focus on questions such as:

> "Did this specific handler execute?"

or

> "Did this callback handler return the expected result?"

**aiogram-bot-tester** takes a different approach.

Even though it is built on top of `aiogram`, the library is intentionally designed to be as framework-agnostic as possible from the test author's perspective.

Your tests should not care about:

- which handler processed the message;
- which router received the update;
- how many middleware layers exist;
- internal implementation details.

Instead, tests should look like a real conversation:

```
User: /start
Bot: Hello! What's your name?

User: Bob
Bot: Hi, Bob! What about your password?

User presses "Continue"
Bot: Please send your password.
```

The test becomes a description of behavior rather than implementation.

## Core Philosophy

To keep tests framework-agnostic and conversational, the library intentionally introduces some limitations.

The core testing model consists of actions such as:

1. Send a message.
2. Receive a response.
3. Press a button.
4. Verify state.
5. Continue the conversation.

This allows tests to read almost like chat transcripts while remaining deterministic and easy to maintain.

## Installation

Install the stable version:

```bash
pip install aiogram_bot_tester
```

Or install the latest development version:

```bash
pip install git+https://github.com/samedit66/aiogram-bot-tester.git
```

The package also installs `pytest-asyncio` for convenience when writing asynchronous tests.

## Understanding the Public API

### What You Should Actually Use

Internally, the library consists of three submodules:

- `bot_tester`
- `types`
- `exceptions`

However, these modules are **implementation details**.

For most projects, you should only work with:

- `BotTester` (from the `bot_tester` submodule)
- `BotMessage` (from the `types` submodule)

Everything else should be treated as **internal machinery**.

### Do Not Test Internal Exceptions

The library exposes several exception types, but they are primarily intended as developer diagnostics.

Avoid writing tests like:

```python
with pytest.raises(ButtonNotFoundError):
    ...
```

The purpose of the library is to test bot behavior, not the implementation details of the testing framework itself.

Focus on **validating the user-visible flow** instead.

## Creating a Tester

There are two ways to create a tester.

### Using Routers (Recommended)

```python
tester = BotTester.from_routers(router)
```

Multiple routers can also be passed:

```python
tester = BotTester.from_routers(
    registration_router,
    admin_router,
    profile_router,
)
```

This is usually the preferred approach because most aiogram applications are organized around routers.

### Using a Dispatcher

For simpler applications:

```python
tester = BotTester.from_dispatcher(dispatcher)
```

This is useful when your bot is small or when routers are not separated.

## Recommended Test Structure

As projects grow, test organization becomes important.

A good approach is to mirror your router structure inside the test directory.

### Example Bot Structure

```
bot/
├── main.py
├── routers/
│   ├── registration.py
│   ├── profile.py
│   ├── admin.py
│   └── support.py
└── services/
    ├── users.py
    └── notifications.py
```

### Recommended Test Structure

```
tests/
├── registration/
│   └── test_registration_flow.py
├── profile/
│   └── test_profile_flow.py
├── admin/
│   └── test_admin_flow.py
└── support/
    └── test_support_flow.py
```

This makes it easy to locate tests corresponding to specific conversation flows.

Even if you use a single dispatcher, organizing tests by user flows is still recommended.

## Sending Messages

The most fundamental operation is sending a user message.

```python
response = await tester.send_message("Hello")
```

The result is always a `BotMessage`.

```python
assert response.contains_text("Hello")
```

### Sending Commands

Commands can be sent directly.

```python
response = await tester.send_command("help")
```

Commands with arguments are also supported.

```python
response = await tester.send_command("sum", 1, 2)
```

This generates:

```
/sum 1 2
```

Example:

```python
response = await tester.send_command("sum", 1, 2)
assert response.contains_text("3")
```

## Starting the Bot

Since `/start` is the most common command, a shortcut exists.

```python
response = await tester.start()
```

Equivalent to:

```python
response = await tester.send_command("start")
```

## Verifying Bot Responses

Every interaction returns a `BotMessage`.

### Checking Text

```python
assert response.contains_text("Hello")
```

Multiple options may be provided:

```python
assert response.contains_text(
    "Hello",
    "Hi",
    "Welcome",
)
```

### Using Regular Expressions

```python
assert response.search_regex(r"\d+")
```

Useful for dynamic content:

```python
assert response.search_regex(
    r"Order #\d+"
)
```

### Working with Buttons

Buttons are first-class citizens in conversational testing.

#### Verify a Button Exists

```python
assert response.has_button("Continue")
```

#### Verify Callback Buttons

```python
assert response.has_callback_button(
    "Continue",
    "continue",
)
```

#### Verify URL Buttons

```python
assert response.has_url_button(
    "Google",
    "https://google.com",
)
```

Remember that URL buttons can be asserted but **cannot be tapped**.

#### Verify Entire Keyboard Layout

```python
assert response.has_keyboard([
    ["Yes", "No"],
    ["Cancel"],
])
```

This is useful when keyboard arrangement itself matters.

#### Interacting with Buttons

The library supports conversational interaction with both reply buttons and callback buttons.

```python
response = await tester.tap_button("Continue")
```

Example flow:

```python
response = await tester.start()
assert response.has_button("Continue")

response = await tester.tap_button("Continue")
assert response.contains_text("Next step")
```

This keeps tests close to how real users interact with the bot.

## Testing FSM State

FSM support is included.

### Verify Current State

```python
assert await tester.in_state(Registration.name)
```

Verify that no state is active:

```python
assert await tester.in_state(None)
```

### Verify FSM Data

```python
assert await tester.data_has(name="Bob")
```

Multiple fields can be checked simultaneously:

```python
assert await tester.data_has(
    name="Bob",
    age=25,
)
```

## Full Conversation Example

The real power of the library appears when testing complete user journeys.

```python
import pytest
import aiogram
from aiogram import F
from aiogram.fsm import context, state
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from aiogram_bot_tester import BotTester


class Registration(state.StatesGroup):
    name = state.State()
    password = state.State()


router = aiogram.Router()


@router.message(aiogram.filters.CommandStart())
async def cmd_start(
    message: Message,
    state: context.FSMContext,
) -> None:
    await message.answer(
        "Hello! What's your name?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Cancel")]
            ],
            resize_keyboard=True,
        ),
    )
    await state.set_state(
        Registration.name
    )


@router.message(
    Registration.name,
    aiogram.F.text,
)
async def name_chosen(
    message: Message,
    state: context.FSMContext,
) -> None:
    await message.answer(
        f"Hi, {message.text}! What about your password?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Continue",
                        callback_data="continue",
                    )
                ]
            ]
        ),
    )

    await state.update_data(
        name=message.text
    )

    await state.set_state(
        Registration.password
    )


@router.callback_query(
    F.data == "continue"
)
async def continue_handler(
    callback: CallbackQuery,
) -> None:
    await callback.message.answer(
        "Please send your password."
    )


@pytest.mark.asyncio
async def test_registration_flow():
    tester = BotTester.from_routers(router)

    response = await tester.start()
    assert response.contains_text("Hello")
    assert response.has_button("Cancel")
    assert await tester.in_state(Registration.name)

    response = await tester.send_message("Bob")
    assert response.contains_text("Hi, Bob!")
    assert response.has_callback_button(
        label="Continue",
        data="continue",
    )
    assert await tester.data_has(name="Bob")
    assert await tester.in_state(Registration.password)

    response = await tester.tap_button("Continue")
    assert response.contains_text("Please send your password.")
```

## What Not to Test

When using `aiogram-bot-tester`, prefer testing behavior:

✅ Good:

```python
response = await tester.start()
assert response.contains_text("Hello")
```

✅ Good:

```python
response = await tester.tap_button("Continue")
assert response.contains_text("Next step")
```

❌ Avoid:

```python
with pytest.raises(
    ButtonNotFoundError
):
    ...
```

The goal is to validate what the user experiences, not how the bot internally reaches that result.
