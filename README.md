# aiogram-bot-tester

[![CI](https://github.com/samedit66/aiogram-bot-tester/actions/workflows/ci-and-publish.yml/badge.svg?branch=main)](https://github.com/samedit66/aiogram-bot-tester/actions/workflows/ci-and-publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/aiogram-bot-tester?logo=pypi)](https://pypi.org/project/aiogram-bot-tester/)
[![Python 3.10–3.15](https://img.shields.io/badge/Python-3.10%E2%80%933.15-blue?logo=python)](https://github.com/samedit66/aiogram-bot-tester/actions/workflows/ci-and-publish.yml)
[![aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-blue?logo=telegram)](https://docs.aiogram.dev/)
[![Apache 2.0 license](https://img.shields.io/badge/license-Apache%202.0-blue)](https://github.com/samedit66/aiogram-bot-tester/blob/main/LICENSE)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/aiogram-bot-tester?period=total&units=INTERNATIONAL_SYSTEM&left_color=GRAY&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/aiogram-bot-tester)

Test aiogram conversations offline. Start the bot, tap a button by its label, and check the reply and the FSM after each step.

```python
import pytest

from my_bot.signup import Signup

pytestmark = pytest.mark.asyncio


async def test_signup(tester):
    welcome = await tester.start()
    welcome.assert_contains("Welcome")
    welcome.assert_button("Sign up")

    prompt = await tester.tap_button("Sign up")
    prompt.assert_contains("What's your name?")
    await tester.assert_state(Signup.name)

    reply = await tester.send_message("Bob")
    reply.assert_contains("Nice to meet you, Bob!")
    await tester.assert_state(Signup.confirm)
    await tester.assert_data(name="Bob")
```

## What you get

- **Actions that read like a chat.** Send a command, tap a reply or inline button by its visible text, or send a photo.
- **A reply you can assert on immediately.** Check text, keyboard layout, media, and captions on the message returned by a step.
- **FSM assertions at the point that matters.** Check transitions and stored data with `assert_state()` and `assert_data()`.
- **Your real aiogram routing, offline.** Run your routers, filters, middleware, and injected dependencies through the dispatcher without a Telegram token or polling.

## Try it with your bot

Install the tester and the async pytest plugin.

```sh
uv add --dev aiogram-bot-tester pytest pytest-asyncio
uv run pytest
```

With pip, install in your test environment.

```sh
python -m pip install aiogram-bot-tester pytest pytest-asyncio
python -m pytest
```

Use your bot's existing router and state group in the examples. Put the fixture in `conftest.py` and the test snippets in a test module with the `pytestmark` from the first example.

```python
import pytest

from aiogram_bot_tester import BotTester
from my_bot.signup import router


@pytest.fixture
def tester():
    return BotTester.from_routers(router)
```

The signup example expects your handlers to show a **Sign up** button on `/start`, prompt for a name when tapped, and store the name before moving to `Signup.confirm`. You can also pass an existing dispatcher to `BotTester.from_dispatcher(dispatcher)`.

## Write tests that match the conversation

### Check a reply on the spot

Each `start()`, `send_message()`, `send_command()`, or `tap_button()` returns the last captured reply for that step. A missing reply raises `NoBotResponseError`.

```python
async def test_welcome_keyboard(tester):
    welcome = await tester.send_command("start")
    welcome.assert_matches(r"^Welcome")
    welcome.assert_keyboard([["Sign up"]])
```

### Replay a transcript

`chat()` replays a linear, text-only conversation and checks that each reply contains the expected text.

```python
async def test_welcome_transcript(tester):
    await tester.chat(
        """
        User: /start
        Bot: Welcome
        """
    )
```

### Send media and check the attachment

Pass media metadata as keyword arguments to `send_photo()`, `send_document()`, `send_voice()`, `send_video()`, or `send_sticker()`. The tester builds the Telegram update for you. For a bot that echoes an uploaded avatar by its file ID:

```python
async def test_avatar(tester):
    reply = await tester.send_photo(file_id="avatar", caption="My avatar")

    reply.assert_photo(file_id="avatar")
    reply.assert_caption("Avatar saved")
    reply.assert_caption_contains("saved")
```

Use `assert_document()`, `assert_voice()`, `assert_video()`, and `assert_sticker()` for other attachments. Captured attachments are available as media models on the reply. Outgoing URLs and upload metadata are available in `tester.api_calls`.

### Send an album

An album contains 2–10 media items. The tester generates a file ID when you omit one. Mix photos and videos, or send a group of documents. Each item reaches your handler as its own update with a shared `media_group_id`. The result contains all captured replies in order, including an empty tuple when the bot stays silent.

```python
from aiogram_bot_tester import Photo


async def test_album(tester):
    replies = await tester.send_album(
        [Photo(file_id="front"), Photo(file_id="back")]
    )

    front, back = replies
    front.assert_photo(file_id="front")
    back.assert_photo(file_id="back")
```

### Feed a custom update

Use `feed_update()` for events such as inline queries. It returns all captured messages and edits from the update. Inspect `api_calls` when the expected outcome is an API call. Each `ApiCall` records the Bot API method name and a read-only snapshot of the supplied parameters.

```python
from aiogram.types import InlineQuery, Update, User


async def test_inline_search(tester):
    replies = await tester.feed_update(
        Update(
            update_id=100,
            inline_query=InlineQuery(
                id="search-1",
                from_user=User(id=1, is_bot=False, first_name="Bob"),
                query="cats",
                offset="",
            ),
        )
    )

    assert replies == ()
    assert any(
        call.method == "answerInlineQuery" and call.params["inline_query_id"] == "search-1"
        for call in tester.api_calls
    )
```

## Why another testing library?

Here is how each tool expresses the same check: send `/start` and verify that the bot replied with a welcome message.

| Library | What you write | When it fits |
| --- | --- | --- |
| **aiogram-bot-tester** | `reply = await tester.start()`<br>`reply.assert_contains("Welcome")` | Follow one conversation step by step and assert directly on replies, buttons, and FSM transitions. |
| [aiogram.test](https://docs.aiogram.dev/en/v3.33.0/dispatcher/testing.html) | `await bot_user.send("/start")`<br>`assert "Welcome" in bot_chat.messages[-1].text` | Model a stateful Telegram environment with multiple users, chats, rights, and an FSM context. |
| [aiogram-testing](https://pypi.org/project/aiogram-testing/) | `calls = await tester.send_message("/start")`<br>`calls.assert_called(SendMessage, text="Welcome")` | Check typed Bot API calls, queue API failures, and read or set FSM state. Its `press()` also accepts a visible inline-button label. |
| [aiogram-test-framework](https://github.com/sgavka/aiogram-test-framework#testuser) | `await user.send_command("start")`<br>`assert user.has_received_message_containing("Welcome")` | Work with simulated users, Telegram object factories, and a request capture log. |

aiogram-bot-tester keeps the common workflow on one object. Create a tester from your router, take a user action, and check the returned reply. Add `await tester.assert_state(...)` and `await tester.assert_data(...)` beside the reply assertion when a step also changes the bot's state.

## Learn more

- [English tutorial](https://github.com/samedit66/aiogram-bot-tester/blob/main/docs/TUTORIAL_EN.MD)
- [Русский туториал](https://github.com/samedit66/aiogram-bot-tester/blob/main/docs/TUTORIAL_RU.md)

> [!WARNING]
> This library is under active development. Its API may change between releases.
