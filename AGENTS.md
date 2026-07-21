# AGENTS.md

## Project: aiogram_bot_tester

A Python library for testing Telegram bots built with aiogram (v3.x). It enables offline, deterministic testing by simulating updates and capturing bot responses without real Telegram API calls.

## Tech Stack

- **Language**: Python 3.10+
- **Framework**: aiogram 3.x (Telegram Bot framework)
- **Testing**: pytest + pytest-asyncio
- **Linting/Formatting**: Ruff
- **Package Manager / Build Tool**: uv (uv.lock, `uv_build` as build backend)

## Project Structure

```
.
├── src/aiogram_bot_tester/       # Package source
│   ├── __init__.py               # Exports: BotTester, BotMessage
│   ├── bot_tester.py             # Core: BotTester, BotConversation classes
│   ├── types.py                  # Dataclasses: Button, CallbackButton, UrlButton, BotMessage
│   └── exceptions.py             # Custom exceptions (BotTesterError hierarchy)
├── tests/                        # Test suite
│   ├── test_api.py               # Unit tests for all public API methods
│   └── test_long_flow.py         # Integration-style test with FSM state machine flow
├── docs/                         # Tutorials (EN / RU)
├── pyproject.toml                # Project config, dependencies, build settings
├── uv.lock                       # Locked dependencies
├── Makefile                      # Dev commands: tests, check, format
└── README.md                     # Documentation and examples
```

## Core Concepts

### BotTester (main entry point)

- `BotTester.from_routers(*routers)` — creates a tester from aiogram Router instances. Routers are deep-copied internally so the same fixture can be reused across multiple test functions without router attachment conflicts.
- `BotTester.from_dispatcher(dispatcher)` — creates a tester from an existing Dispatcher instance.

### BotConversation (internal)

- Wraps a Dispatcher with a mocked aiohttp session.
- Intercepts Telegram API calls via `mock.AsyncMock` in `_capture_request`.
- Captures outgoing messages as `BotMessage` objects for assertion.
- Feeds simulated updates through the dispatcher's update pipeline using `dispatcher.feed_update()`.

### BotMessage (assertion helper)

Immutable dataclass with convenience methods:
- `contains(*texts)` — checks if message text contains any of the given strings
- `matches(*patterns)` — `re.search` matching against any given pattern
- `has_button(label)` — checks for any button by label
- `has_callback_button(label, callback_data)` — checks inline callback button
- `has_url_button(label, url)` — checks inline URL button
- `has_keyboard(keyboard)` — exact match of keyboard layout matrix
- `assert_*` / `refute_*` helpers — provide readable assertion failures for text,
  regex, button, and keyboard checks

### FSM Support

The tester uses aiogram's built-in `MemoryStorage` for FSM state management. Test code can:
- Check current state via `tester.in_state(state)`
- Inspect stored data via `tester.data_has(**kwargs)`
- Assert or refute state and data via `assert_state`, `refute_state`,
  `assert_data`, and `refute_data`

## Development Commands

| Command | Description |
|---------|-------------|
| `make tests` | Run pytest with verbose output (`uv run pytest -vv`) |
| `make check` | Run ruff linter (`uv run ruff check`) |
| `make format` | Run ruff formatter (`uv run ruff format`) |

## Dependencies

- **Runtime**: `aiogram>=3.28.2`, `pytest-asyncio>=1.3.0`
- **Dev**: `pytest>=9.0.3`, `ruff>=0.15.13`

All dependencies are managed by uv. Use `uv sync` to install.

## Writing Tests

Tests use pytest fixtures with `BotTester.from_routers()`. The router is deep-copied per test instance, so fixtures are safe:

```python
@pytest.fixture
def tester():
    return BotTester.from_routers(my_router)

@pytest.mark.asyncio
async def test_flow(tester):
    response = await tester.start()
    response.assert_contains("Hello")
    response.assert_button("Continue")
```

## Exception Hierarchy

All exceptions inherit from `BotTesterError`:
- `NoBotMessageError` — no bot message exists yet (e.g., tapping button before any bot response)
- `NoBotResponseError` — bot did not respond to a user action
- `ButtonNotFoundError` — specified button label not found in last bot message
- `UrlButtonInteractionError` — attempting to tap a URL button (unsupported)
- `AmbiguousButtonError` — multiple buttons share the same label
- `InvalidTranscriptError` — raised when transcript format is malformed in `chat()`

## Design Notes

1. **Button tapping by label, not callback_data**: Users interact with button labels visually, so `tap_button(label)` finds the matching button internally rather than requiring raw callback_data.

2. **Router deep-copying**: Routers are deep-copied when passed to `from_routers()` because aiogram routers can only be attached to one dispatcher. This prevents issues when a tester fixture is used across multiple test functions.

3. **Mocked API calls**: The aiohttp session's `make_request` is replaced with an AsyncMock that intercepts TelegramMethod calls and captures SendMessage content as BotMessage objects. No network requests are made.

4. **Declarative chat testing**: `tester.chat(transcript)` replays a transcript of user/bot messages and asserts bot responses match expected text.

### Declarative Testing with `chat()`

The `chat()` method enables natural-language conversation tests:

```python
@pytest.mark.asyncio
async def test_registration(tester):
    await tester.chat(
        """
        User: /start
        Bot: Hello! What's your name?

        User: Bob
        Bot: Hi, Bob! Welcome.
        """
    )
```

**Format rules:**
- Each conversation turn is a block with exactly 2 lines: `User:` followed by `Bot:`
- Blocks are separated by blank lines
- Bot text is asserted via substring match (`assert_contains`)
- Only text messages supported (no button tapping in v1)

**Exception:** `InvalidTranscriptError` — raised when transcript format is malformed.
