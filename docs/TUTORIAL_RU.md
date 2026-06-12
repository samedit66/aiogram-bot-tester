# Руководство по aiogram-bot-tester

## Введение

Тестирование — одна из самых важных частей разработки ПО. Telegram-боты не исключение. Хорошо продуманный набор тестов даёт уверенность, что новые фичи не ломают существующий функционал, и позволяет команде двигаться быстрее.

В идеальной архитектуре Telegram-бот содержит минимум логики внутри хендлеров. Хендлеры должны только принимать апдейты, вызывать бизнес-сервисы и возвращать ответы. Вся бизнес-логика должна жить в отдельном пакете и покрываться unit-тестами независимо от бота.

Но в реальности всё часто выглядит иначе.

Многие Telegram-боты развиваются очень быстро, и значительная часть логики постепенно оказывается внутри хендлеров, FSM-сценариев, callback-обработчиков и цепочек роутеров. Да, вынести всё в сервисы архитектурно чище, но если делать это слишком рано, можно легко уйти в оверинжиниринг и затормозить выпуск самого продукта.

Именно эту проблему и решает **aiogram-bot-tester**.

Вместо тестирования отдельных хендлеров в изоляции библиотека позволяет тестировать **полный диалоговый сценарий** бота офлайн и детерминированно.

## Чем aiogram-bot-tester отличается от других решений?

Многие библиотеки для тестирования Telegram-ботов сосредоточены на вопросах вроде:

> «Выполнился ли этот конкретный хендлер?»

или

> «Вернул ли этот callback-хендлер ожидаемый результат?»

**aiogram-bot-tester** смотрит на задачу иначе.

Несмотря на то что библиотека построена поверх `aiogram`, с точки зрения автора тестов она специально спроектирована максимально независимо от фреймворка.

Ваши тесты не должны зависеть от:

- того, какой именно хендлер обработал сообщение;
- того, какой роутер получил апдейт;
- количества middleware в цепочке;
- внутренних деталей реализации.

Вместо этого тест должен выглядеть как реальный диалог:

```text
Пользователь: /start
Бот: Привет! Как тебя зовут?

Пользователь: Bob
Бот: Привет, Bob! Теперь нужен пароль.

Пользователь нажимает «Продолжить»
Бот: Отправь, пожалуйста, свой пароль.
```

Тест становится описанием поведения, а не реализации.

## Основная философия

Чтобы тесты оставались разговорными и не зависели от внутреннего устройства приложения, библиотека намеренно вводит некоторые ограничения.

Базовая модель тестирования состоит из следующих действий:

1. Отправить сообщение.
2. Получить ответ.
3. Нажать кнопку.
4. Проверить состояние.
5. Продолжить диалог.

Благодаря этому тесты читаются почти как лог переписки, оставаясь при этом детерминированными и простыми в поддержке.

## Установка

Установка стабильной версии:

```bash
pip install aiogram_bot_tester
```

Установка последней dev-версии:

```bash
pip install git+https://github.com/samedit66/aiogram-bot-tester.git
```

Для удобства написания асинхронных тестов пакет также устанавливает `pytest-asyncio`.

## Публичный API

### Что действительно стоит использовать

Внутри библиотека состоит из трёх подмодулей:

- `bot_tester`
- `types`
- `exceptions`

Но это **внутренние детали реализации**.

Для большинства проектов вам понадобятся только:

- `BotTester` (из подмодуля `bot_tester`)
- `BotMessage` (из подмодуля `types`)

Всё остальное лучше воспринимать как внутреннюю механику библиотеки.

### Не тестируйте внутренние исключения

Библиотека экспортирует несколько типов исключений, но в первую очередь они предназначены для диагностики и отладки.

Не стоит писать тесты такого вида:

```python
with pytest.raises(ButtonNotFoundError):
    ...
```

Задача библиотеки — тестировать поведение бота, а не детали реализации тестового фреймворка.

Фокусируйтесь на **проверке пользовательского сценария**.

## Создание тестера

Существует два способа создать тестер.

### Через роутеры (рекомендуется)

```python
tester = BotTester.from_routers(router)
```

Можно передать сразу несколько роутеров:

```python
tester = BotTester.from_routers(
    registration_router,
    admin_router,
    profile_router,
)
```

Обычно это лучший вариант, поскольку большинство приложений на aiogram организованы именно вокруг роутеров.

### Через Dispatcher

Для более простых приложений:

```python
tester = BotTester.from_dispatcher(dispatcher)
```

Подходит для небольших ботов или проектов без разделения на роутеры.

## Рекомендуемая структура тестов

По мере роста проекта организация тестов становится всё важнее.

Хорошая практика — отражать структуру роутеров внутри каталога с тестами.

### Структура бота

```text
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

### Рекомендуемая структура тестов

```text
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

Так гораздо проще находить тесты, относящиеся к конкретным пользовательским сценариям.

Даже если вы используете один dispatcher, всё равно рекомендуется группировать тесты по пользовательским флоу.

## Отправка сообщений

Самая базовая операция — отправка сообщения от пользователя.

```python
response = await tester.send_message("Hello")
```

Результатом всегда будет объект `BotMessage`.

```python
assert response.contains_text("Hello")
```

### Отправка команд

Команды можно отправлять напрямую.

```python
response = await tester.send_command("help")
```

Поддерживаются и команды с аргументами.

```python
response = await tester.send_command("sum", 1, 2)
```

Это сгенерирует:

```text
/sum 1 2
```

Пример:

```python
response = await tester.send_command("sum", 1, 2)
assert response.contains_text("3")
```

## Запуск бота

Так как `/start` используется чаще всего, для него есть отдельный шорткат.

```python
response = await tester.start()
```

Эквивалентно:

```python
response = await tester.send_command("start")
```

## Проверка ответов бота

Каждое взаимодействие возвращает объект `BotMessage`.

### Проверка текста

```python
assert response.contains_text("Hello")
```

Можно передать несколько вариантов:

```python
assert response.contains_text(
    "Hello",
    "Hi",
    "Welcome",
)
```

### Использование регулярных выражений

```python
assert response.search_regex(r"\d+")
```

Полезно для динамического контента:

```python
assert response.search_regex(
    r"Order #\d+"
)
```

### Работа с кнопками

Кнопки являются полноценной частью диалогового тестирования.

#### Проверка наличия кнопки

```python
assert response.has_button("Continue")
```

#### Проверка callback-кнопки

```python
assert response.has_callback_button(
    "Continue",
    "continue",
)
```

#### Проверка URL-кнопки

```python
assert response.has_url_button(
    "Google",
    "https://google.com",
)
```

Помните, что URL-кнопки можно проверять, но **нажимать их нельзя**.

#### Проверка всей раскладки клавиатуры

```python
assert response.has_keyboard([
    ["Yes", "No"],
    ["Cancel"],
])
```

Полезно, когда важно именно расположение кнопок.

#### Взаимодействие с кнопками

Библиотека поддерживает работу как с reply-кнопками, так и с callback-кнопками.

```python
response = await tester.tap_button("Continue")
```

Пример сценария:

```python
response = await tester.start()
assert response.has_button("Continue")

response = await tester.tap_button("Continue")
assert response.contains_text("Next step")
```

Так тест остаётся максимально близким к реальному поведению пользователя.

## Тестирование FSM

Поддержка FSM встроена в библиотеку.

### Проверка текущего состояния

```python
assert await tester.in_state(Registration.name)
```

Проверка отсутствия активного состояния:

```python
assert await tester.in_state(None)
```

### Проверка данных FSM

```python
assert await tester.data_has(name="Bob")
```

Можно проверять сразу несколько полей:

```python
assert await tester.data_has(
    name="Bob",
    age=25,
)
```

## Полный пример диалога

Настоящая сила библиотеки раскрывается при тестировании полноценных пользовательских сценариев.

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

## Что не стоит тестировать

При использовании `aiogram-bot-tester` старайтесь тестировать поведение.

✅ Хорошо:

```python
response = await tester.start()
assert response.contains_text("Hello")
```

✅ Хорошо:

```python
response = await tester.tap_button("Continue")
assert response.contains_text("Next step")
```

❌ Избегайте:

```python
with pytest.raises(
    ButtonNotFoundError
):
    ...
```

Цель — проверить то, что видит и ощущает пользователь, а не внутренний путь, которым бот пришёл к результату.
