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

При создании тестера можно передать middleware. Это удобно для внедрения тестовых зависимостей, например фейкового репозитория:

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

Middleware применяются к сообщениям и callback query в порядке их передачи.

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
response.assert_contains("Hello")
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
assert response.text == "3"
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

В тестах предпочтительно использовать встроенные методы `assert_*` и
`refute_*`: проверки получаются более декларативными, а при падении показывают
понятное сообщение с ожидаемыми и фактическими значениями. Булевы предикаты
остаются доступными для составных пользовательских условий.

### Проверка текста

```python
response.assert_contains("Hello")
```

Можно передать несколько вариантов:

```python
response.assert_contains(
    "Hello",
    "Hi",
    "Welcome",
)
```

Если передано несколько значений, проверка проходит, когда ответ содержит хотя
бы одно из них. `refute_contains()` проверяет, что ни одного значения нет:

```python
response.refute_contains("Error", "Exception")
```

Для точного сравнения используйте публичный атрибут `text`. В таком виде pytest
также покажет стандартный diff строк:

```python
assert response.text == "Hello!"
```

### Использование регулярных выражений

```python
response.assert_matches(r"\d+")
```

Полезно для динамического контента:

```python
response.assert_matches(
    r"Order #\d+",
    r"Invoice #\d+",
)
```

Как и `assert_contains()`, несколько паттернов используют семантику «хотя бы
один», а поиск выполняется через `re.search()`. `refute_matches()` проверяет,
что ни один паттерн не встречается:

```python
response.refute_matches(r"Traceback", r"Exception")
```

### Работа с кнопками

Кнопки являются полноценной частью диалогового тестирования.

#### Проверка наличия кнопки

```python
response.assert_button("Continue")
```

#### Проверка callback-кнопки

```python
response.assert_callback_button(
    "Continue",
    callback_data="continue",
)
```

#### Проверка URL-кнопки

```python
response.assert_url_button(
    "Google",
    url="https://google.com",
)
```

Помните, что URL-кнопки можно проверять, но **нажимать их нельзя**.

#### Проверка всей раскладки клавиатуры

```python
response.assert_keyboard([
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
response.assert_button("Continue")

response = await tester.tap_button("Continue")
response.assert_contains("Next step")
```

Так тест остаётся максимально близким к реальному поведению пользователя.

## Тестирование FSM

Поддержка FSM встроена в библиотеку.

### Проверка текущего состояния

```python
await tester.assert_state(Registration.name)
```

Проверка отсутствия активного состояния:

```python
await tester.assert_state(None)
```

### Проверка данных FSM

```python
await tester.assert_data(name="Bob")
```

Можно проверять сразу несколько полей:

```python
await tester.assert_data(
    name="Bob",
    age=25,
)
```

Для отрицательных проверок предусмотрены `refute_state()` и `refute_data()`.

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

## Декларативное тестирование через `chat()`

Для простых диалоговых сценариев библиотека предоставляет более лаконичный способ написания тестов — метод `chat()`. Вместо цепочки отдельных взаимодействий вы описываете весь разговор как транскрипт:

```python
@pytest.mark.asyncio
async def test_registration_flow():
    tester = BotTester.from_routers(router)

    await tester.chat(
        """
        User: /start
        Bot: Привет! Как тебя зовут?

        User: Bob
        Bot: Привет, Bob! Теперь нужен пароль.
        """
    )
```

### Правила формата

- Каждый оборот диалога состоит ровно из двух строк: `User:` затем `Bot:`
- Обороты разделяются пустыми строками (двойной перевод строки)
- Текст после `User:` отправляется как сообщение пользователя боту
- Текст после `Bot:` проверяется как подстрока в ответе бота через `assert_contains`

### Обработка ошибок

Если формат транскрипта неверен, будет выброшено исключение `InvalidTranscriptError`:

```python
from aiogram_bot_tester.exceptions import InvalidTranscriptError

with pytest.raises(InvalidTranscriptError):
    await tester.chat(
        """
        User: /start
        Bot: Привет!

        Эта строка без префикса User.
        Bot: Ответ
        """
    )
```

### Когда использовать `chat()`, а не пошаговый API

Используйте `chat()`, когда хотите получить компактное, читаемое описание диалога — похоже на то, как читается спецификация продукта или пользовательская история. Идеально подходит для простых линейных сценариев.

Используйте пошаговый API (`send_message`, `tap_button`, `in_state` и т.д.), когда нужны промежуточные проверки, проверка состояния FSM или верификация кнопок между взаимодействиями:

```python
@pytest.mark.asyncio
async def test_with_intermediate_checks():
    tester = BotTester.from_routers(router)

    response = await tester.start()
    response.assert_button("Cancel")  # Проверяем клавиатуру перед продолжением

    await tester.chat(
        """
        User: Bob
        Bot: Привет, Bob! Теперь нужен пароль.
        """
    )

    await tester.assert_state(Registration.password)  # Проверяем состояние FSM
```

## Что не стоит тестировать

При использовании `aiogram-bot-tester` старайтесь тестировать поведение.

✅ Хорошо:

```python
response = await tester.start()
response.assert_contains("Hello")
```

✅ Хорошо:

```python
response = await tester.tap_button("Continue")
response.assert_contains("Next step")
```

❌ Избегайте:

```python
with pytest.raises(
    ButtonNotFoundError
):
    ...
```

Цель — проверить то, что видит и ощущает пользователь, а не внутренний путь, которым бот пришёл к результату.
