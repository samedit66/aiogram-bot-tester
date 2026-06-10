# aiogram_bot_tester

![aiogram](https://img.shields.io/badge/aiogram-3.x-blue?logo=telegram)
![telegram](https://img.shields.io/badge/telegram-bot-blue?logo=telegram)
![status](https://img.shields.io/badge/status-WIP-orange)
![python](https://img.shields.io/badge/python-3.10+-blue?logo=python)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/aiogram-bot-tester?period=total&units=INTERNATIONAL_SYSTEM&left_color=GRAY&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/aiogram-bot-tester)

A lightweight testing utility for **offline testing of aiogram bots without real Telegram API calls**.

Its goal is to make it easy to test bot logic deterministically by simulating Telegram updates, intercepting bot API calls, and exposing a clean, assertion-friendly response layer.

Легковесная библиотека для **оффлайн-тестирования ботов, написанных на aiogram, без использования реального Telegram API**.

Цель пакета — сделать проверку логики бота простой и предсказуемой за счет симуляции Telegram-обновлений, перехвата вызовов bot API и удобного слоя для проверок.

## Installation / Установка

Stable version / Стабильная версия:

```bash
pip install aiogram_bot_tester
```

Latest development version / Последняя версия из репозитория:

```bash
pip install git+https://github.com/samedit66/aiogram-bot-tester.git
```

> [!NOTE]
> `aiogram_bot_tester` also installs `pytest-asyncio` for async tests.
> The library itself does not depend on it directly; it is included for convenience.
>
> `aiogram_bot_tester` также устанавливает `pytest-asyncio` для асинхронных тестов.
> Сама библиотека не зависит от него напрямую; пакет добавлен для удобства.

## Quick example / Пример

```python
import pytest
import aiogram
from aiogram import filters, types

from aiogram_bot_tester import BotTester

router = aiogram.Router()


@router.message(filters.CommandStart())
async def cmd_start(message: types.Message) -> None:
    await message.answer("Hello! What's your name?")


@pytest.mark.asyncio
async def test_it() -> None:
    tester = BotTester.from_routers(router)

    # For simpler cases when you have only a `Dispatcher`:
    # tester = BotTester.from_dispatcher(dispatcher)

    # Send a "/start" command
    response = await tester.start()
    assert response.contains_text("Hello")
```

## Public API / Публичный API

### BotTester.from_routers(*routers, **kwargs)

Construct a `BotTester` instance from one or more `aiogram.Router` objects.

```python
tester = BotTester.from_routers(router)
```

### BotTester.from_dispatcher(dispatcher, **kwargs)

Construct a `BotTester` instance from an existing dispatcher.

```python
tester = BotTester.from_dispatcher(dispatcher)
```

### send_message(text, timeout=None)

Send a user message to the bot.

Returns a `BotMessage`. If the bot does not produce any response, `NoBotResponseError` is raised.

```python
response = await tester.send_message("/start")
assert response.contains_text("Hello")
```

### send_command(command, *args, prefix="/")

Send a command to the bot.

Each positional argument is converted to `str` and appended to the command.

```python
response = await tester.send_command("sum", 1, 2)
assert response.contains_text("3")
```

### start()

Shortcut for `send_command("start")`.

```python
response = await tester.start()
```

### tap_button(label, timeout=None)

Tap a button attached to the last bot message.

Reply buttons and inline callback buttons are supported. URL buttons are not tappable; they can only be asserted with `has_url_button()`.

If there is no last bot message, `NoBotMessageError` is raised.
If the button does not exist, `ButtonNotFoundError` is raised.
If several buttons with the same label exist, `AmbiguousButtonError` is raised.
If the bot does not produce a response after the tap, `NoBotResponseError` is raised.
If the target button is a URL button, `UrlButtonInteractionError` is raised.

```python
response = await tester.tap_button("Next")
```

### in_state(state)

Return `True` when the bot is currently in the given FSM state.

```python
assert await tester.in_state(Form.name)
assert await tester.in_state(None)
```

### data_has(**kwargs)

Return `True` when the FSM data contains all the provided key-value pairs.

```python
assert await tester.data_has(name="Bob")
```

## BotMessage assertions / Проверки BotMessage

Each call that returns a bot response gives you a `BotMessage` object.

### contains_text(*texts)

Return `True` if the message text contains any of the provided substrings.

```python
assert response.contains_text("Hello", "Hi")
```

### search_regex(*patterns)

Return `True` if the message text matches any of the provided regular expressions.

Patterns may be strings or compiled `re.Pattern` objects.

```python
assert response.search_regex(r"\d+")
```

### has_button(label)

Return `True` if the message contains a button with the given label.

```python
assert response.has_button("Yes")
```

### has_callback_button(label, callback_data)

Return `True` if the message contains an inline callback button with the given label and callback data.

```python
assert response.has_callback_button("Press", "press")
```

### has_url_button(label, url)

Return `True` if the message contains a URL button with the given label and URL.

```python
assert response.has_url_button("Google", "https://google.com")
```

### has_keyboard(keyboard)

Return `True` if the message keyboard matches the provided matrix of button labels.

```python
assert response.has_keyboard([
    ["Yes", "No"],
    ["Cancel"],
])
```

## Errors / Ошибки

The public API uses specific exceptions:

- `NoBotResponseError` — the bot did not answer.
- `NoBotMessageError` — an operation requires a previous bot message.
- `ButtonNotFoundError` — the requested button was not found.
- `AmbiguousButtonError` — more than one button with the same label was found.
- `UrlButtonInteractionError` — a URL button was tapped, but URL buttons cannot be interacted with in tests.

Публичный API использует специальные исключения:

- `NoBotResponseError` — бот не ответил.
- `NoBotMessageError` — операция требует предыдущего сообщения от бота.
- `ButtonNotFoundError` — нужная кнопка не найдена.
- `AmbiguousButtonError` — найдено несколько кнопок с одинаковой подписью.
- `UrlButtonInteractionError` — была нажата URL-кнопка, но такие кнопки нельзя взаимодействовать в тестах.

## Full example / Полный пример

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
async def cmd_start(message: Message, state: context.FSMContext) -> None:
    await message.answer(
        "Hello! What's your name?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Cancel")]],
            resize_keyboard=True,
        ),
    )
    await state.set_state(Registration.name)


@router.message(Registration.name, aiogram.F.text)
async def name_chosen(message: Message, state: context.FSMContext) -> None:
    name = message.text
    await message.answer(
        f"Hi, {name}! What about your password?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Continue", callback_data="continue")]
            ],
        ),
    )
    await state.update_data(name=name)
    await state.set_state(Registration.password)


@router.callback_query(F.data == "continue")
async def on_continue(callback: CallbackQuery) -> None:
    await callback.message.answer("Please send your password.")


@pytest.mark.asyncio
async def test_full_flow() -> None:
    tester = BotTester.from_routers(router)

    response = await tester.start()
    assert response.contains_text("Hello")
    assert response.has_button("Cancel")
    assert await tester.in_state(Registration.name)

    response = await tester.send_message("Bob")
    assert response.contains_text("Hi, Bob!")
    assert response.has_callback_button("Continue", "continue")
    assert await tester.data_has(name="Bob")
    assert await tester.in_state(Registration.password)

    response = await tester.tap_button("Continue")
    assert response.contains_text("Please send your password.")
```
