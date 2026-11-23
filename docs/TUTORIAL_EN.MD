# aiogram-bot-tester Tutorial

`aiogram-bot-tester` is a library for testing Telegram bots built with aiogram
3.x offline. It feeds simulated updates to a dispatcher and lets you verify bot
responses, keyboards, callback buttons, and FSM state without starting polling
or contacting Telegram.

## Table of Contents

- [Why Test Telegram Bots](#why-test-telegram-bots)
- [How the Library Works](#how-the-library-works)
- [Requirements and Installation](#requirements-and-installation)
- [Your First Test: an Echo Bot](#your-first-test-an-echo-bot)
- [Creating a BotTester](#creating-a-bottester)
  - [From a Dispatcher](#from-a-dispatcher)
  - [From Routers](#from-routers)
  - [Dependencies and Middleware](#dependencies-and-middleware)
  - [Test User Parameters](#test-user-parameters)
- [BotTester Methods](#bottester-methods)
  - [send_message](#send_message)
  - [Sending media](#sending-media)
  - [send_album](#send_album)
  - [feed_update](#feed_update)
  - [send_command](#send_command)
  - [start](#start)
  - [tap_button](#tap_button)
  - [in_state and data_has](#in_state-and-data_has)
  - [assert_state and refute_state](#assert_state-and-refute_state)
  - [assert_data and refute_data](#assert_data-and-refute_data)
  - [chat](#chat)
- [The BotMessage Object](#the-botmessage-object)
  - [Fields, buttons, and is_empty](#fields-buttons-and-is_empty)
  - [Checking Text](#checking-text)
  - [Checking Media and Captions](#checking-media-and-captions)
  - [Checking Buttons](#checking-buttons)
  - [Checking the Keyboard](#checking-the-keyboard)
- [Exceptions](#exceptions)
- [Complete Example: Registration with FSM](#complete-example-registration-with-fsm)
- [How to Structure Tests](#how-to-structure-tests)
- [Practical Recommendations and Limitations](#practical-recommendations-and-limitations)

## Why Test Telegram Bots

Tests protect existing flows from regressions, make refactoring safer, and let
you ship changes with confidence. For a Telegram bot, it is useful to test not
only individual functions but also the behavior visible to a user:

- which response follows a command or message;
- which buttons are shown and what happens when they are pressed;
- which FSM state the conversation enters;
- which data is retained between steps;
- how the bot behaves throughout a complete user journey.

In an ideal architecture, handlers receive updates, call services, and format
responses, while business logic lives in separate modules covered by fast unit
tests. This is a useful direction, but it is not a universal rule.

In small or rapidly evolving bots, logic often lives in handlers, FSM
transitions, and callback chains. Extracting a separate business layer may
sometimes be irrelevant or take longer than the feature itself. In that case,
testing the real flow through handlers can be simpler and faster. A practical
test suite usually combines both approaches:

- test complex calculations and business rules with unit tests;
- test routing, responses, buttons, dependencies, and FSM behavior with
  `aiogram-bot-tester`.

## How the Library Works

The Telegram Bot API is the HTTP API through which a bot receives updates and
performs actions such as sending messages, editing them, and sending media.
Normally, aiogram calls this API on behalf of your bot.

`aiogram-bot-tester` makes no real network requests. It:

1. creates test `Message`, `CallbackQuery`, and `Update` objects;
2. passes them to `Dispatcher.feed_update()`;
3. uses an offline aiogram session;
4. intercepts Telegram Bot API calls;
5. converts `SendMessage` calls into `BotMessage` objects.

The tests are therefore offline and deterministic. You do not need a real bot
token, and no messages are sent to real users.

`BotMessage` captures the text and keyboards of sent messages and chat message
edits. Use `tester.api_calls` to inspect outgoing calls such as media sends or
deletions.

The convenience methods such as `send_message()` return the last captured
message. `feed_update()` returns all captured responses for the update.

## Requirements and Installation

Requirements:

- Python 3.10 or newer;
- aiogram 3.x;
- pytest;
- pytest-asyncio.

Install the stable version:

```bash
pip install aiogram_bot_tester
```

Or install the latest version from the repository:

```bash
pip install git+https://github.com/samedit66/aiogram-bot-tester.git
```

`pytest` and `pytest-asyncio` are installed separately with `pip install pytest pytest-asyncio`. Every asynchronous test
in this tutorial is decorated with `@pytest.mark.asyncio`:

```python
import pytest


@pytest.mark.asyncio
async def test_something() -> None:
    ...
```

Import the public classes from the package root:

```python
from aiogram_bot_tester import BotMessage, BotTester
```

## Your First Test: an Echo Bot

Start with the classic setup: one `Dispatcher` and one handler. The echo bot
returns the text it receives.

```python
import pytest
from aiogram import Dispatcher
from aiogram.types import Message

from aiogram_bot_tester import BotTester


dispatcher = Dispatcher()


@dispatcher.message()
async def echo(message: Message) -> None:
    await message.answer(message.text or "")


@pytest.mark.asyncio
async def test_echo() -> None:
    tester = BotTester.from_dispatcher(dispatcher)

    response = await tester.send_message("Hello!")

    assert response.text == "Hello!"
```

`send_message()` passes a simulated message through the real dispatcher
pipeline. The handler runs normally, while the mock session intercepts
`message.answer()`.

## Creating a BotTester

### From a Dispatcher

```python
BotTester.from_dispatcher(dispatcher, **kwargs)
```

Parameters:

- `dispatcher` — a configured `aiogram.Dispatcher`;
- `**kwargs` — test conversation parameters described below.

Use this form when your application already assembles a dispatcher with
routers, middleware, dependencies, and storage:

```python
tester = BotTester.from_dispatcher(dispatcher)
```

The method returns a new `BotTester` and raises no library-specific exceptions
on its own.

### From Routers

```python
BotTester.from_routers(
    *routers,
    dependencies=None,
    middlewares=None,
    **kwargs,
)
```

Parameters:

- `*routers` — one or more `aiogram.Router` objects;
- `dependencies` — a mapping of names to objects made available through aiogram
  dependency injection;
- `middlewares` — inner middleware for `message` and `callback_query` events;
- `**kwargs` — test conversation parameters.

```python
tester = BotTester.from_routers(
    registration_router,
    profile_router,
)
```

The library creates a `Dispatcher` with `MemoryStorage` and deep-copies each
router before attaching it. A router can therefore be used in a fixture invoked
by multiple tests. Middleware instances are not copied.

### Dependencies and Middleware

The names in `dependencies` must match handler arguments:

```python
class FakeRepository:
    async def get_name(self, user_id: int) -> str:
        return "Bob"


@router.message(Command("profile"))
async def profile(message: Message, repository: FakeRepository) -> None:
    name = await repository.get_name(message.from_user.id)
    await message.answer(name)


tester = BotTester.from_routers(
    router,
    dependencies={"repository": FakeRepository()},
)
```

Middleware run in the order in which they are passed:

```python
tester = BotTester.from_routers(
    router,
    middlewares=[AuthMiddleware(), LoggingMiddleware()],
)
```

For outer middleware or other event types, configure a dispatcher directly and
use `from_dispatcher()`.

### Test User Parameters

Both factory methods pass `**kwargs` to the test conversation:

- `token: str = "42:TEST"` — a syntactically valid fake token;
- `chat_id: int = 1` — test chat ID;
- `user_id: int = 1` — test user ID;
- `user_first_name: str = "Test"` — test user's first name.

```python
tester = BotTester.from_routers(
    router,
    chat_id=100,
    user_id=42,
    user_first_name="Alice",
)
```

Do not pass a real Telegram token: network requests are mocked.

## BotTester Methods

Methods that model a user action and expect a bot response—`send_message()`,
`send_command()`, `start()`, and `tap_button()`—return the last `BotMessage`.
Predicate methods return `bool`; assertion methods and `chat()` return `None`.

### send_message

```python
await tester.send_message(text, timeout=None)
```

Parameters:

- `text: str` — user message text;
- `timeout: int | None` — seconds to wait **after**
  `Dispatcher.feed_update()` and before checking for a response.

```python
@pytest.mark.asyncio
async def test_greeting() -> None:
    response = await tester.send_message("Alice")
    response.assert_contains("Hello, Alice")
```

If the bot sends no response, `NoBotResponseError` is raised.

`timeout` is not a deadline and does not interrupt a slow handler. The
dispatcher first finishes processing the update, then the library calls
`asyncio.sleep(timeout)`, and only then checks for a response.

### Sending media

Pass media metadata as keyword arguments. The tester builds an incoming
message for the current chat and user. When you omit `file_id`, it generates
one for you. Files are simulated through their metadata.

| Method | Media-specific parameters |
| --- | --- |
| `send_photo()` | `width=640`, `height=480` |
| `send_document()` | `file_name=None`, `mime_type=None` |
| `send_voice()` | `duration=1` in seconds, `mime_type=None` |
| `send_video()` | `width=640`, `height=480`, `duration=1` in seconds |
| `send_sticker()` | `emoji=None` for a static sticker |

All five methods accept `file_id` and `timeout`. The first four also accept
`caption` and a tuple of `CaptionEntity` objects from `aiogram_bot_tester` as
`caption_entities`. Invalid metadata, such as a photo with zero width, raises
`ValueError` before the handler runs.

Suppose your bot acknowledges each attachment with a text message:

```python
@pytest.mark.asyncio
async def test_uploads(tester) -> None:
    response = await tester.send_photo(file_id="avatar", caption="My avatar")
    response.assert_contains("Photo received")

    response = await tester.send_document(file_name="orders.csv", mime_type="text/csv")
    response.assert_contains("Document received")

    response = await tester.send_voice(duration=12, mime_type="audio/ogg")
    response.assert_contains("Voice message received")

    response = await tester.send_video(width=1280, height=720, duration=8)
    response.assert_contains("Video received")

    response = await tester.send_sticker(emoji="🙂")
    response.assert_contains("Sticker received")
```

Each method returns the last captured reply. If your bot stays silent, it
raises `NoBotResponseError`, just like `send_message()`.

### send_album

Use `send_album()` for 2–10 attachments. Import `Photo`, `Video`, or
`Document` from `aiogram_bot_tester`. Photos and videos can share an album.
Documents form their own album. Invalid size or a mix of documents and other
attachments raises `ValueError` before the first update.

Suppose the bot acknowledges each item in order:

```python
from aiogram_bot_tester import Photo, Video


@pytest.mark.asyncio
async def test_upload_album(tester) -> None:
    photo_reply, video_reply = await tester.send_album(
        [
            Photo(file_id="cover", caption="Cover"),
            Video(file_id="walkthrough", duration=8),
        ]
    )

    photo_reply.assert_contains("Photo received")
    video_reply.assert_contains("Video received")
```

The dispatcher receives a separate update per item, with a common
`media_group_id` on all the incoming messages. The method returns all captured
replies in order, or an empty tuple if the bot stays silent. It applies
`timeout` once after dispatching the last item.

### feed_update

Use `feed_update(update)` to pass an aiogram `Update` directly to the
dispatcher. Use this for fully specified events, such as a photo with multiple sizes or
an inline query.

The result is a tuple of captured messages and edits in order. An update that
produces no captured message returns an empty tuple. Use `tester.api_calls` to
inspect outgoing calls. Each `ApiCall` has a Telegram API method name
(`call.method`) and a read-only parameter snapshot (`call.params`).

```python
from datetime import datetime, timezone

import pytest
from aiogram import F, Router
from aiogram.types import Chat, Message, PhotoSize, Update, User

from aiogram_bot_tester import BotTester

router = Router()


@router.message(F.photo)
async def receive_photo(message: Message) -> None:
    await message.answer("Photo received.")


@pytest.mark.asyncio
async def test_incoming_photo() -> None:
    tester = BotTester.from_routers(router)
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

### send_command

```python
await tester.send_command(command, *args, command_prefix="/")
```

Parameters:

- `command: str` — command name without the prefix;
- `*args: object` — arguments, each converted with `str`;
- `command_prefix: str` — command prefix, `/` by default.

```python
@pytest.mark.asyncio
async def test_sum() -> None:
    response = await tester.send_command("sum", 1, 2)
    assert response.text == "3"
```

The bot receives `/sum 1 2`. The prefix can be changed:

```python
response = await tester.send_command("help", command_prefix="!")
```

The method calls `send_message()` without a timeout and raises
`NoBotResponseError` if the bot does not respond.

### start

```python
await tester.start()
```

A parameterless shortcut for `await tester.send_command("start")`.

```python
@pytest.mark.asyncio
async def test_start() -> None:
    response = await tester.start()
    response.assert_contains("Welcome")
```

If the bot does not respond to `/start`, `NoBotResponseError` is raised.

### tap_button

```python
await tester.tap_button(label, timeout=None)
```

Parameters:

- `label: str` — visible text of a button in the bot's last message;
- `timeout: int | None` — post-processing wait with the same semantics as in
  `send_message()`.

For a reply button, the library sends its label as a regular user message. For a
callback button, it creates a `CallbackQuery` with the corresponding
`callback_data`.

```python
@pytest.mark.asyncio
async def test_continue_button() -> None:
    response = await tester.start()
    response.assert_button("Continue")

    response = await tester.tap_button("Continue")
    response.assert_contains("Next step")
```

Exceptions:

- `NoBotMessageError` — the bot has not sent a message yet;
- `ButtonNotFoundError` — no button has that label;
- `AmbiguousButtonError` — several buttons have the same label;
- `UrlButtonInteractionError` — the matching button opens a URL;
- `NoBotResponseError` — the action was handled but produced no response.

A URL button can be asserted through `BotMessage`, but cannot be "pressed":
opening a browser is outside the conversation with the bot.

### in_state and data_has

```python
await tester.in_state(state)
await tester.data_has(**kwargs)
```

`in_state(state)` accepts `aiogram.fsm.state.State` or `None` and reports whether
the current state matches. `None` means that no FSM state is active.

`data_has(**kwargs)` returns `True` only if FSM data contains every supplied
key-value pair.

```python
@pytest.mark.asyncio
async def test_state_predicates() -> None:
    assert await tester.in_state(Registration.name)
    assert await tester.data_has(source="start", attempts=1)
```

These methods raise no library-specific exceptions.

### assert_state and refute_state

```python
await tester.assert_state(state)
await tester.refute_state(state)
```

Both methods accept `State | None`.

- `assert_state()` requires the current state to equal the argument;
- `refute_state()` requires the states to differ.

```python
@pytest.mark.asyncio
async def test_registration_state() -> None:
    await tester.assert_state(Registration.name)
    await tester.refute_state(Registration.password)
```

A failed condition raises `AssertionError` with the expected and actual state.

### assert_data and refute_data

```python
await tester.assert_data(**kwargs)
await tester.refute_data(**kwargs)
```

- `assert_data()` requires every supplied pair to be present;
- `refute_data()` succeeds if at least one pair is absent or has a different
  value.

```python
@pytest.mark.asyncio
async def test_registration_data() -> None:
    await tester.assert_data(name="Bob", age=25)
    await tester.refute_data(name="Alice", age=25)
```

A failed condition raises `AssertionError`.

### chat

```python
await tester.chat(transcript)
```

`transcript: str` describes a linear conversation. Each block has exactly two
non-empty lines, and blocks are separated by a blank line:

```python
@pytest.mark.asyncio
async def test_greeting_chat() -> None:
    await tester.chat(
        """
        User: /start
        Bot: What is your name?

        User: Bob
        Bot: Hello, Bob!
        """
    )
```

Text after `User:` is sent through `send_message()`. Text after `Bot:` is
checked as a substring through `BotMessage.assert_contains()`.

`chat()` boundaries:

- only linear pairs of text messages;
- button presses cannot be represented;
- intermediate FSM and keyboard checks cannot be placed inside the transcript;
- each response uses substring matching rather than exact equality.

For buttons, FSM, and branching, combine `chat()` with the step-by-step API or
use only the step-by-step API.

Exceptions:

- `InvalidTranscriptError` — incorrect line count or missing `User:`/`Bot:`
  prefix;
- `NoBotResponseError` — the bot did not answer one of the messages;
- `AssertionError` — the response did not contain the expected text.

## The BotMessage Object

`BotMessage` is an immutable dataclass representing a captured bot reply or message edit.
You normally do not construct it yourself; `BotTester` methods return it.

### Fields, buttons, and is_empty

Public fields:

- `text: str | None` — response text;
- `caption: str | None` — media caption;
- `photo`, `document`, `voice`, `video`, `sticker` — captured attachments;
- `media_group_id: str | None` — identifier of the captured media group;
- `keyboard: list[list[Button]]` — rows of the captured keyboard.

Buttons are represented by:

- `Button(label)` — reply button;
- `CallbackButton(label, data)` — inline callback button;
- `UrlButton(label, url)` — inline URL button.

`message.buttons` is a property that flattens `keyboard` into a single list.
`message.is_empty()` returns `True` when the message has no text, keyboard,
caption, or media.

```python
assert response.text == "Choose an action"
assert [button.label for button in response.buttons] == ["Yes", "No"]
assert not response.is_empty()
```

These operations raise no special exceptions.

### Checking Text

```python
message.contains(text, *texts) -> bool
message.matches(pattern, *patterns) -> bool
message.assert_contains(text, *texts) -> None
message.refute_contains(text, *texts) -> None
message.assert_matches(pattern, *patterns) -> None
message.refute_matches(pattern, *patterns) -> None
```

`contains()` returns `True` if the message text contains at least one supplied
string. `matches()` uses `re.search()` and accepts strings or compiled
`re.Pattern` objects.

```python
assert response.contains("Hello", "Welcome")
assert response.matches(r"Order #\d+")
```

Assert variants require at least one value to match. Refute variants require no
value to match:

```python
response.assert_contains("Hello", "Welcome")
response.refute_contains("Error", "Traceback")
response.assert_matches(r"Order #\d+", r"Invoice #\d+")
response.refute_matches(r"failed", r"exception")
```

Every method requires at least one text or pattern. Boolean methods return
`False` when `text is None`. Assert/refute methods raise `AssertionError` when
their condition fails.

For exact comparison, use the `text` field:

```python
assert response.text == "Hello!"
```

### Checking Media and Captions

Call these methods on the response that contains the attachment.

| Method | What it checks |
| --- | --- |
| `assert_photo(file_id=None)` | A photo exists. A supplied ID can match any of its sizes. |
| `assert_document(file_id=None, file_name=None)` | A document exists and each supplied field matches exactly. |
| `assert_voice(file_id=None)` | A voice message exists and its ID matches if supplied. |
| `assert_video(file_id=None)` | A video exists and its ID matches if supplied. |
| `assert_sticker(file_id=None, emoji=None)` | A sticker exists and each supplied field matches exactly. |
| `assert_caption(expected)` | The full caption matches. Pass `None` to check for no caption. |
| `assert_caption_contains(text, *texts)` | The caption contains at least one of the strings. |

Pass attachment filters by keyword. All these assertions raise
`AssertionError` on a mismatch. A filter for unavailable metadata also fails.
For example, when a bot sends a document by file ID alone, the tester has no
file name to check. Caption checks read `response.caption`.

In this example, each command makes the bot send an attachment:

```python
@pytest.mark.asyncio
async def test_media_replies(tester) -> None:
    photo = await tester.send_command("avatar")
    photo.assert_photo(file_id="saved-avatar")
    photo.assert_caption("Avatar saved")
    photo.assert_caption_contains("updated", "saved")

    document = await tester.send_command("report")
    document.assert_document(file_name="report.pdf")

    voice = await tester.send_command("preview")
    voice.assert_voice(file_id="voice-preview")
    voice.assert_caption(None)

    video = await tester.send_command("demo")
    video.assert_video(file_id="video-demo")

    sticker = await tester.send_command("thanks")
    sticker.assert_sticker(emoji="🙂")
```

### Checking Buttons

```python
message.has_button(label) -> bool
message.assert_button(label) -> None
message.refute_button(label) -> None
```

These methods check the label of any button type:

```python
assert response.has_button("Continue")
response.assert_button("Continue")
response.refute_button("Delete")
```

For URL buttons:

```python
message.has_url_button(label, *, url) -> bool
message.assert_url_button(label, *, url) -> None
message.refute_url_button(label, *, url) -> None
```

Both arguments must match; `url` is keyword-only:

```python
assert response.has_url_button(
    "Documentation",
    url="https://example.com/docs",
)
response.assert_url_button(
    "Documentation",
    url="https://example.com/docs",
)
response.refute_url_button(
    "Delete",
    url="https://example.com/delete",
)
```

For callback buttons:

```python
message.has_callback_button(label, *, callback_data) -> bool
message.assert_callback_button(label, *, callback_data) -> None
message.refute_callback_button(label, *, callback_data) -> None
```

`callback_data` is keyword-only, and both label and data must match:

```python
assert response.has_callback_button("Yes", callback_data="confirm")
response.assert_callback_button("Yes", callback_data="confirm")
response.refute_callback_button("No", callback_data="confirm")
```

Boolean methods return `True` or `False`. Assert/refute methods raise
`AssertionError` when their condition fails.

### Checking the Keyboard

```python
message.has_keyboard(keyboard) -> bool
message.assert_keyboard(keyboard) -> None
message.refute_keyboard(keyboard) -> None
```

`keyboard: list[list[str]]` is a matrix of labels. Every row, every button, and
their order must match:

```python
expected = [
    ["Yes", "No"],
    ["Cancel"],
]

assert response.has_keyboard(expected)
response.assert_keyboard(expected)
response.refute_keyboard([["Delete"]])
```

`has_keyboard()` returns `bool`; assertion variants raise `AssertionError` when
their condition fails.

## Exceptions

All library-specific exceptions inherit from `BotTesterError`:

| Exception | When it is raised |
|---|---|
| `NoBotMessageError` | an action requires a previous bot message |
| `NoBotResponseError` | the bot sends no response to an action |
| `ButtonNotFoundError` | no button has the requested label |
| `AmbiguousButtonError` | several buttons have the requested label |
| `UrlButtonInteractionError` | a test attempts to press a URL button |
| `InvalidTranscriptError` | a `chat()` transcript is malformed |

`assert_*` and `refute_*` methods use the standard `AssertionError`, allowing
pytest to report them as normal assertion failures.

Knowing the exceptions is useful when diagnosing a failed test. You normally do
not need to test that the library itself raises them: your test's purpose is to
verify your bot's behavior.

## Complete Example: Registration with FSM

The following bot asks for a name and password, stores the data, finishes the
FSM, and confirms registration.

```python
import pytest
from aiogram import Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from aiogram_bot_tester import BotTester


class Registration(StatesGroup):
    name = State()
    confirmation = State()
    password = State()


dispatcher = Dispatcher()


@dispatcher.message(CommandStart())
async def start_registration(message: Message, state: FSMContext) -> None:
    await state.set_state(Registration.name)
    await message.answer("What is your name?")


@dispatcher.message(Registration.name, F.text)
async def save_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)
    await state.set_state(Registration.confirmation)
    await message.answer(
        f"Save the name {message.text}?",
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


@dispatcher.callback_query(
    Registration.confirmation,
    F.data == "continue",
)
async def request_password(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.set_state(Registration.password)
    await callback.message.answer("Send your password.")


@dispatcher.message(Registration.password, F.text)
async def save_password(message: Message, state: FSMContext) -> None:
    await state.update_data(password=message.text)
    data = await state.get_data()
    await state.clear()
    await message.answer(f"User {data['name']} has been registered.")


@pytest.mark.asyncio
async def test_registration_flow() -> None:
    tester = BotTester.from_dispatcher(dispatcher)

    response = await tester.start()
    response.assert_contains("What is your name?")
    await tester.assert_state(Registration.name)

    response = await tester.send_message("Bob")
    response.assert_contains("Save the name Bob?")
    response.assert_callback_button(
        "Continue",
        callback_data="continue",
    )
    await tester.assert_data(name="Bob")
    await tester.assert_state(Registration.confirmation)

    response = await tester.tap_button("Continue")
    response.assert_contains("Send your password.")
    await tester.assert_state(Registration.password)

    response = await tester.send_message("secret")
    response.assert_contains("User Bob has been registered.")
    await tester.assert_state(None)
    await tester.refute_data(name="Bob")
    await tester.refute_data(password="secret")
```

After `state.clear()`, both the FSM state and data have been removed.

## How to Structure Tests

There is no single "correct" directory structure. Choose one that makes the
test for a particular behavior easy to find. For example:

```text
bot/
├── main.py
├── routers/
│   ├── registration.py
│   └── profile.py
└── services/
    └── users.py

tests/
├── conftest.py
├── unit/
│   └── test_users_service.py
└── flows/
    ├── test_registration.py
    └── test_profile.py
```

- `tests/unit/` tests business rules without Telegram or aiogram;
- `tests/flows/` tests handlers and user journeys;
- `conftest.py` stores shared fixtures and fake dependencies.

Example fixture:

```python
import pytest

from aiogram_bot_tester import BotTester
from bot.routers.registration import router


@pytest.fixture
def tester() -> BotTester:
    return BotTester.from_routers(router)
```

Each test receives a new `BotTester`, a new `Dispatcher`, and new
`MemoryStorage`, preventing FSM state and data from leaking between tests.
Routers are deep-copied, so the fixture can be safely reused:

```python
@pytest.mark.asyncio
async def test_registration(tester: BotTester) -> None:
    response = await tester.start()
    response.assert_contains("What is your name?")


@pytest.mark.asyncio
async def test_unexpected_message(tester: BotTester) -> None:
    response = await tester.send_message("???")
    response.assert_contains("Unknown command")
```

## Practical Recommendations and Limitations

- Test user-visible behavior rather than the name of the handler that ran.
- Use `response.text` for exact text and `assert_contains()` or
  `assert_matches()` for more resilient flows.
- Test cancellation, invalid input, repeated callbacks, and fallback handlers,
  not only the happy path.
- Extract computational business logic into unit tests when it improves the
  design, but do not postpone a useful flow test solely for an "ideal"
  architecture.
- Create a new tester for each test to isolate FSM state.
- Remember that interaction methods return the last response when several
  `SendMessage` calls occur.
- `timeout` is an extra wait after processing, not a deadline.
- `chat()` supports only linear text conversations. Use the step-by-step API for
  buttons, FSM assertions, and branching.
- Tests need neither a real Telegram token nor a network connection.
