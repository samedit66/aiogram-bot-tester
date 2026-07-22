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

Middleware can be passed when creating a tester. This is useful for injecting test dependencies, such as a fake repository:

```python
class RepositoryMiddleware(BaseMiddleware):
    def __init__(self, repository):
        self.repository = repository

    async def __call__(self, handler, event, data):
        data["repository"] = self.repository
        return await handler(event, data)


class FakeRepository:
    async def get_name(self, user_id: int) -> str:
        return "Bob"


tester = BotTester.from_routers(
    router,
    middlewares=[RepositoryMiddleware(FakeRepository())],
)

response = await tester.send_message("/profile")
response.assert_contains("Bob")
```

Middleware are applied to messages and callback queries in the order in which they are passed.

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
response.assert_contains("Hello")
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
assert response.text == "3"
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

Prefer the built-in `assert_*` and `refute_*` methods in tests. They make checks
more declarative and provide clear failure messages with the expected and actual
values. The boolean predicates remain available when you need to compose a
custom condition.

### Checking Text

```python
response.assert_contains("Hello")
```

Multiple options may be provided:

```python
response.assert_contains(
    "Hello",
    "Hi",
    "Welcome",
)
```

When several values are passed, the assertion succeeds if the message contains
at least one of them. Use `refute_contains()` to assert that none are present:

```python
response.refute_contains("Error", "Exception")
```

For an exact comparison, check the public `text` attribute directly. This also
lets pytest show its standard string diff:

```python
assert response.text == "Hello!"
```

### Using Regular Expressions

```python
response.assert_matches(r"\d+")
```

Useful for dynamic content:

```python
response.assert_matches(
    r"Order #\d+",
    r"Invoice #\d+",
)
```

As with `assert_contains()`, multiple patterns use “any” semantics and matching
is performed with `re.search()`. Use `refute_matches()` to require that none of
the patterns occur:

```python
response.refute_matches(r"Traceback", r"Exception")
```

### Working with Buttons

Buttons are first-class citizens in conversational testing.

#### Verify a Button Exists

```python
response.assert_button("Continue")
```

#### Verify Callback Buttons

```python
response.assert_callback_button(
    "Continue",
    callback_data="continue",
)
```

#### Verify URL Buttons

```python
response.assert_url_button(
    "Google",
    url="https://google.com",
)
```

Remember that URL buttons can be asserted but **cannot be tapped**.

#### Verify Entire Keyboard Layout

```python
response.assert_keyboard([
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
response.assert_button("Continue")

response = await tester.tap_button("Continue")
response.assert_contains("Next step")
```

This keeps tests close to how real users interact with the bot.

## Testing FSM State

FSM support is included.

### Verify Current State

```python
await tester.assert_state(Registration.name)
```

Verify that no state is active:

```python
await tester.assert_state(None)
```

### Verify FSM Data

```python
await tester.assert_data(name="Bob")
```

Multiple fields can be checked simultaneously:

```python
await tester.assert_data(
    name="Bob",
    age=25,
)
```

The corresponding negative checks are `refute_state()` and `refute_data()`.

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
    response.assert_contains("Hello")
    response.assert_button("Cancel")
    await tester.assert_state(Registration.name)

    response = await tester.send_message("Bob")
    response.assert_contains("Hi, Bob!")
    response.assert_callback_button(
        label="Continue",
        callback_data="continue",
    )
    await tester.assert_data(name="Bob")
    await tester.assert_state(Registration.password)

    response = await tester.tap_button("Continue")
    response.assert_contains("Please send your password.")
```

## Declarative Testing with `chat()`

For simple conversational flows, the library provides a more concise way to write tests using the `chat()` method. Instead of chaining individual interactions, you describe the entire conversation as a transcript:

```python
@pytest.mark.asyncio
async def test_registration_flow():
    tester = BotTester.from_routers(router)

    await tester.chat(
        """
        User: /start
        Bot: Hello! What's your name?

        User: Bob
        Bot: Hi, Bob! What about your password?
        """
    )
```

### Format Rules

- Each conversation turn consists of exactly two lines: `User:` followed by `Bot:`
- Turns are separated by blank lines (double newline)
- The text after `User:` is sent as a user message to the bot
- The text after `Bot:` is asserted as a substring match against the bot's response using `assert_contains`

### Error Handling

If the transcript format is incorrect, an `InvalidTranscriptError` is raised:

```python
from aiogram_bot_tester.exceptions import InvalidTranscriptError

with pytest.raises(InvalidTranscriptError):
    await tester.chat(
        """
        User: /start
        Bot: Hello!

        This line has no User prefix.
        Bot: Response
        """
    )
```

### When to Use `chat()` vs Step-by-Step API

Use `chat()` when you want a compact, readable description of a conversation flow — similar to how a product spec or user story reads. It's ideal for straightforward linear flows.

Use the step-by-step API (`send_message`, `tap_button`, `in_state`, etc.) when you need intermediate assertions, FSM state checks, or button verification between interactions:

```python
@pytest.mark.asyncio
async def test_with_intermediate_checks():
    tester = BotTester.from_routers(router)

    response = await tester.start()
    response.assert_button("Cancel")  # Check keyboard before proceeding

    await tester.chat(
        """
        User: Bob
        Bot: Hi, Bob! What about your password?
        """
    )

    await tester.assert_state(Registration.password)  # Check FSM state
```

## What Not to Test

When using `aiogram-bot-tester`, prefer testing behavior:

✅ Good:

```python
response = await tester.start()
response.assert_contains("Hello")
```

✅ Good:

```python
response = await tester.tap_button("Continue")
response.assert_contains("Next step")
```

❌ Avoid:

```python
with pytest.raises(
    ButtonNotFoundError
):
    ...
```

The goal is to validate what the user experiences, not how the bot internally reaches that result.
