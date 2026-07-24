# Руководство по aiogram-bot-tester

`aiogram-bot-tester` — библиотека для офлайн-тестирования Telegram-ботов,
написанных на aiogram 3.x. Она отправляет в dispatcher искусственные обновления и
позволяет проверять ответы бота, клавиатуры, callback-кнопки и состояние FSM без
запуска polling и без обращения к Telegram.

## Оглавление

- [Зачем тестировать Telegram-ботов](#зачем-тестировать-telegram-ботов)
- [Как работает библиотека](#как-работает-библиотека)
- [Требования и установка](#требования-и-установка)
- [Первый тест: echo-бот](#первый-тест-echo-бот)
- [Создание BotTester](#создание-bottester)
  - [Из Dispatcher](#из-dispatcher)
  - [Из Router](#из-router)
  - [Зависимости и middleware](#зависимости-и-middleware)
  - [Параметры тестового пользователя](#параметры-тестового-пользователя)
- [Методы BotTester](#методы-bottester)
  - [send_message](#send_message)
  - [send_command](#send_command)
  - [start](#start)
  - [tap_button](#tap_button)
  - [in_state и data_has](#in_state-и-data_has)
  - [assert_state и refute_state](#assert_state-и-refute_state)
  - [assert_data и refute_data](#assert_data-и-refute_data)
  - [chat](#chat)
- [Объект BotMessage](#объект-botmessage)
  - [Поля, buttons и is_empty](#поля-buttons-и-is_empty)
  - [Проверка текста](#проверка-текста)
  - [Проверка кнопок](#проверка-кнопок)
  - [Проверка клавиатуры](#проверка-клавиатуры)
- [Исключения](#исключения)
- [Полный пример: регистрация с FSM](#полный-пример-регистрация-с-fsm)
- [Как структурировать тесты](#как-структурировать-тесты)
- [Практические рекомендации и ограничения](#практические-рекомендации-и-ограничения)

## Зачем тестировать Telegram-ботов

Тесты защищают существующие сценарии от регрессий, упрощают рефакторинг и
позволяют выпускать изменения увереннее. Для Telegram-бота важно проверять не
только отдельные функции, но и поведение, которое видит пользователь:

- какой ответ приходит на команду или сообщение;
- какие кнопки показаны и что происходит после нажатия;
- в какое состояние FSM переходит диалог;
- какие данные сохраняются между шагами;
- как бот ведёт себя в полном пользовательском сценарии.

В идеальной архитектуре хендлеры принимают обновления, вызывают сервисы и
формируют ответы, а бизнес-логика находится в отдельных модулях и покрывается
быстрыми unit-тестами. Это полезный ориентир, но не универсальное правило.

В небольших и быстро развивающихся ботах логика часто находится в хендлерах,
FSM-переходах и callback-цепочках. Иногда выделение отдельного слоя бизнес-логики
неактуально или потребует больше времени, чем само изменение. В такой ситуации
тест реального сценария через хендлеры может быть проще и быстрее. Обычно полезно
сочетать оба подхода:

- сложные вычисления и правила проверять unit-тестами;
- маршрутизацию, ответы, кнопки, зависимости и FSM проверять через
  `aiogram-bot-tester`.

## Как работает библиотека

Telegram Bot API — HTTP API, через который бот получает обновления и выполняет
действия: отправляет сообщения, редактирует их, отправляет медиа и так далее. В
обычном приложении aiogram обращается к этому API от имени бота.

`aiogram-bot-tester` не делает реальных сетевых запросов. Библиотека:

1. создаёт тестовые объекты `Message`, `CallbackQuery` и `Update`;
2. передаёт их в `Dispatcher.feed_update()`;
3. подменяет HTTP-сессию aiogram mock-объектом;
4. перехватывает вызовы Telegram Bot API;
5. преобразует вызовы `SendMessage` в объекты `BotMessage`.

Поэтому тесты работают офлайн и детерминированно: токен настоящего бота не нужен,
а сообщения не отправляются реальным пользователям.

Сейчас содержимое ответа полноценно захватывается для метода Telegram Bot API
`SendMessage`: текст, reply-клавиатура, inline callback-кнопки и inline
URL-кнопки.

> [!WARNING]
> Пока не поддерживается полноценная проверка отправки фото, видео, документов,
> стикеров и других медиа, а также редактирования и удаления сообщений и прочих
> Telegram methods, отличных от `SendMessage`. Не используйте текущий
> `BotMessage` для утверждений о содержимом таких вызовов.

Если в ответ на одно действие хендлер вызывает `message.answer()` несколько раз,
внутренне захватываются все сообщения, но публичный метод возвращает **последний**
захваченный `BotMessage`.

## Требования и установка

Требования:

- Python 3.10 или новее;
- aiogram 3.x;
- pytest;
- pytest-asyncio.

Установите стабильную версию:

```bash
pip install aiogram_bot_tester
```

Или последнюю версию из репозитория:

```bash
pip install git+https://github.com/samedit66/aiogram-bot-tester.git
```

`pytest-asyncio` устанавливается как зависимость библиотеки. Каждый асинхронный
тест в этом руководстве декорирован `@pytest.mark.asyncio`:

```python
import pytest


@pytest.mark.asyncio
async def test_something() -> None:
    ...
```

Импортируйте публичные классы из корня пакета:

```python
from aiogram_bot_tester import BotMessage, BotTester
```

## Первый тест: echo-бот

Начнём с классического варианта: один `Dispatcher` и один хендлер. Echo-бот
возвращает пользователю полученный текст.

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

    response = await tester.send_message("Привет!")

    assert response.text == "Привет!"
```

`send_message()` передаёт искусственное сообщение в настоящий pipeline
dispatcher. Хендлер выполняется как обычно, а `message.answer()` перехватывается
mock-сессией.

## Создание BotTester

### Из Dispatcher

```python
BotTester.from_dispatcher(dispatcher, **kwargs)
```

Параметры:

- `dispatcher` — настроенный `aiogram.Dispatcher`;
- `**kwargs` — параметры тестового диалога, описанные ниже.

Используйте этот вариант, если приложение уже собирает dispatcher с роутерами,
middleware, зависимостями и storage:

```python
tester = BotTester.from_dispatcher(dispatcher)
```

Метод возвращает новый `BotTester` и сам по себе исключений библиотеки не
выбрасывает.

### Из Router

```python
BotTester.from_routers(
    *routers,
    dependencies=None,
    middlewares=None,
    **kwargs,
)
```

Параметры:

- `*routers` — один или несколько `aiogram.Router`;
- `dependencies` — отображение имён в объекты, доступные хендлерам через
  dependency injection aiogram;
- `middlewares` — список inner middleware для событий `message` и
  `callback_query`;
- `**kwargs` — параметры тестового диалога.

```python
tester = BotTester.from_routers(
    registration_router,
    profile_router,
)
```

Библиотека создаёт `Dispatcher` с `MemoryStorage` и глубоко копирует каждый
router перед подключением. Благодаря этому один router можно использовать в
fixture, вызываемой несколькими тестами. Экземпляры middleware не копируются.

### Зависимости и middleware

Имена из `dependencies` должны совпадать с аргументами хендлера:

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

Middleware передаются в порядке выполнения:

```python
tester = BotTester.from_routers(
    router,
    middlewares=[AuthMiddleware(), LoggingMiddleware()],
)
```

Для outer middleware и других типов событий настройте dispatcher вручную и
используйте `from_dispatcher()`.

### Параметры тестового пользователя

Оба фабричных метода передают `**kwargs` тестовому диалогу:

- `token: str = "42:TEST"` — синтаксически корректный фиктивный токен;
- `chat_id: int = 1` — идентификатор тестового чата;
- `user_id: int = 1` — идентификатор тестового пользователя;
- `user_first_name: str = "Test"` — имя тестового пользователя.

```python
tester = BotTester.from_routers(
    router,
    chat_id=100,
    user_id=42,
    user_first_name="Alice",
)
```

Настоящий Telegram token передавать не нужно: сетевые запросы замоканы.

## Методы BotTester

Методы, моделирующие действие пользователя и ожидающие ответ бота,
`send_message()`, `send_command()`, `start()` и `tap_button()`, возвращают
последний `BotMessage`. Методы-предикаты возвращают `bool`, методы утверждений и
`chat()` — `None`.

### send_message

```python
await tester.send_message(text, timeout=None)
```

Параметры:

- `text: str` — текст сообщения пользователя;
- `timeout: int | None` — сколько секунд подождать **после**
  `Dispatcher.feed_update()` и до проверки ответа.

```python
@pytest.mark.asyncio
async def test_greeting() -> None:
    response = await tester.send_message("Alice")
    response.assert_contains("Hello, Alice")
```

Если бот не отправил ни одного ответа, выбрасывается `NoBotResponseError`.

`timeout` не является дедлайном и не прерывает медленный хендлер. Сначала
dispatcher полностью обрабатывает update, затем библиотека выполняет
`asyncio.sleep(timeout)`, и только после этого проверяет наличие ответа.

### send_command

```python
await tester.send_command(command, *args, command_prefix="/")
```

Параметры:

- `command: str` — имя команды без префикса;
- `*args: object` — аргументы, каждый из которых преобразуется через `str`;
- `command_prefix: str` — префикс команды, по умолчанию `/`.

```python
@pytest.mark.asyncio
async def test_sum() -> None:
    response = await tester.send_command("sum", 1, 2)
    assert response.text == "3"
```

В бот будет отправлен текст `/sum 1 2`. Можно изменить префикс:

```python
response = await tester.send_command("help", command_prefix="!")
```

Метод вызывает `send_message()` без timeout и выбрасывает `NoBotResponseError`,
если бот не ответил.

### start

```python
await tester.start()
```

Shortcut для `await tester.send_command("start")`. Параметров нет.

```python
@pytest.mark.asyncio
async def test_start() -> None:
    response = await tester.start()
    response.assert_contains("Welcome")
```

Если бот не отвечает на `/start`, выбрасывается `NoBotResponseError`.

### tap_button

```python
await tester.tap_button(label, timeout=None)
```

Параметры:

- `label: str` — видимый текст кнопки в последнем сообщении бота;
- `timeout: int | None` — ожидание после обработки действия, с той же семантикой,
  что у `send_message()`.

Для reply-кнопки библиотека отправляет её label как обычное сообщение. Для
callback-кнопки создаётся `CallbackQuery` с соответствующим `callback_data`.

```python
@pytest.mark.asyncio
async def test_continue_button() -> None:
    response = await tester.start()
    response.assert_button("Продолжить")

    response = await tester.tap_button("Продолжить")
    response.assert_contains("Следующий шаг")
```

Исключения:

- `NoBotMessageError` — бот ещё не отправлял сообщений;
- `ButtonNotFoundError` — кнопка с таким label отсутствует;
- `AmbiguousButtonError` — в сообщении несколько кнопок с одинаковым label;
- `UrlButtonInteractionError` — найденная кнопка открывает URL;
- `NoBotResponseError` — действие обработано, но бот не отправил ответ.

URL-кнопку можно проверить через `BotMessage`, но нельзя «нажать»: открытие
браузера находится за пределами диалога с ботом.

### in_state и data_has

```python
await tester.in_state(state)
await tester.data_has(**kwargs)
```

`in_state(state)` принимает `aiogram.fsm.state.State` или `None` и возвращает,
совпадает ли текущее состояние с ожидаемым. `None` означает отсутствие активного
состояния.

`data_has(**kwargs)` возвращает `True`, только если в FSM data присутствуют все
переданные пары ключ–значение.

```python
@pytest.mark.asyncio
async def test_state_predicates() -> None:
    assert await tester.in_state(Registration.name)
    assert await tester.data_has(source="start", attempts=1)
```

Эти методы не выбрасывают специальных исключений библиотеки.

### assert_state и refute_state

```python
await tester.assert_state(state)
await tester.refute_state(state)
```

Оба метода принимают `State | None`.

- `assert_state()` требует совпадения текущего состояния с переданным;
- `refute_state()` требует, чтобы состояния не совпадали.

```python
@pytest.mark.asyncio
async def test_registration_state() -> None:
    await tester.assert_state(Registration.name)
    await tester.refute_state(Registration.password)
```

При невыполнении условия выбрасывается `AssertionError` с ожидаемым и
фактическим состоянием.

### assert_data и refute_data

```python
await tester.assert_data(**kwargs)
await tester.refute_data(**kwargs)
```

- `assert_data()` требует присутствия всех переданных пар;
- `refute_data()` проходит, если хотя бы одна пара отсутствует или имеет другое
  значение.

```python
@pytest.mark.asyncio
async def test_registration_data() -> None:
    await tester.assert_data(name="Bob", age=25)
    await tester.refute_data(name="Alice", age=25)
```

При невыполнении условия выбрасывается `AssertionError`.

### chat

```python
await tester.chat(transcript)
```

`transcript: str` описывает линейный разговор. Каждый блок содержит ровно две
непустые строки, а блоки разделяются пустой строкой:

```python
@pytest.mark.asyncio
async def test_greeting_chat() -> None:
    await tester.chat(
        """
        User: /start
        Bot: Как вас зовут?

        User: Bob
        Bot: Привет, Bob!
        """
    )
```

Текст после `User:` отправляется через `send_message()`. Текст после `Bot:`
проверяется как подстрока через `BotMessage.assert_contains()`.

Границы `chat()`:

- только линейные пары текстовых сообщений;
- нельзя описывать нажатия кнопок;
- нельзя помещать промежуточные проверки FSM или клавиатуры внутрь transcript;
- каждый ответ проверяется только по вхождению текста, а не по точному равенству.

Для кнопок, FSM и сложных ветвлений сочетайте `chat()` с пошаговым API или
используйте только пошаговый API.

Исключения:

- `InvalidTranscriptError` — неверное число строк или отсутствует префикс
  `User:`/`Bot:`;
- `NoBotResponseError` — бот не ответил на одно из сообщений;
- `AssertionError` — ответ не содержит ожидаемый текст.

## Объект BotMessage

`BotMessage` — неизменяемый dataclass, представляющий захваченный `SendMessage`.
Обычно его не создают вручную: он возвращается методами `BotTester`.

### Поля, buttons и is_empty

Публичные поля:

- `text: str | None` — текст ответа;
- `keyboard: list[list[Button]]` — строки захваченной клавиатуры.

Кнопки представлены типами:

- `Button(label)` — reply-кнопка;
- `CallbackButton(label, data)` — inline callback-кнопка;
- `UrlButton(label, url)` — inline URL-кнопка.

`message.buttons` — property, разворачивающий матрицу `keyboard` в плоский список.
`message.is_empty()` возвращает `True`, если у сообщения нет непустого текста и
клавиатуры.

```python
assert response.text == "Выберите действие"
assert [button.label for button in response.buttons] == ["Да", "Нет"]
assert not response.is_empty()
```

Эти операции специальных исключений не выбрасывают.

### Проверка текста

```python
message.contains(text, *texts) -> bool
message.matches(pattern, *patterns) -> bool
message.assert_contains(text, *texts) -> None
message.refute_contains(text, *texts) -> None
message.assert_matches(pattern, *patterns) -> None
message.refute_matches(pattern, *patterns) -> None
```

`contains()` возвращает `True`, если текст сообщения содержит хотя бы одну
переданную строку. `matches()` использует `re.search()` и принимает строки или
скомпилированные `re.Pattern`.

```python
assert response.contains("Hello", "Welcome")
assert response.matches(r"Order #\d+")
```

Assert-варианты требуют совпадение хотя бы с одним значением. Refute-варианты
требуют, чтобы не совпало ни одно:

```python
response.assert_contains("Hello", "Welcome")
response.refute_contains("Error", "Traceback")
response.assert_matches(r"Order #\d+", r"Invoice #\d+")
response.refute_matches(r"failed", r"exception")
```

Каждый метод требует минимум одну строку или pattern. Булевы методы возвращают
`False`, если `text is None`. Assert/refute-методы выбрасывают `AssertionError`
при невыполнении условия.

Для точного сравнения используйте поле `text`:

```python
assert response.text == "Hello!"
```

### Проверка кнопок

```python
message.has_button(label) -> bool
message.assert_button(label) -> None
message.refute_button(label) -> None
```

Эти методы проверяют label кнопки любого типа:

```python
assert response.has_button("Продолжить")
response.assert_button("Продолжить")
response.refute_button("Удалить")
```

Для URL-кнопок:

```python
message.has_url_button(label, *, url) -> bool
message.assert_url_button(label, *, url) -> None
message.refute_url_button(label, *, url) -> None
```

Оба параметра должны совпасть; `url` является keyword-only:

```python
assert response.has_url_button(
    "Документация",
    url="https://example.com/docs",
)
response.assert_url_button(
    "Документация",
    url="https://example.com/docs",
)
response.refute_url_button(
    "Удалить",
    url="https://example.com/delete",
)
```

Для callback-кнопок:

```python
message.has_callback_button(label, *, callback_data) -> bool
message.assert_callback_button(label, *, callback_data) -> None
message.refute_callback_button(label, *, callback_data) -> None
```

`callback_data` является keyword-only, label и данные должны совпасть:

```python
assert response.has_callback_button("Да", callback_data="confirm")
response.assert_callback_button("Да", callback_data="confirm")
response.refute_callback_button("Нет", callback_data="confirm")
```

Булевы методы возвращают `True` или `False`. Assert/refute-методы выбрасывают
`AssertionError` при невыполнении условия.

### Проверка клавиатуры

```python
message.has_keyboard(keyboard) -> bool
message.assert_keyboard(keyboard) -> None
message.refute_keyboard(keyboard) -> None
```

`keyboard: list[list[str]]` — матрица label. Учитываются все строки, порядок и
наличие всех кнопок:

```python
expected = [
    ["Да", "Нет"],
    ["Отмена"],
]

assert response.has_keyboard(expected)
response.assert_keyboard(expected)
response.refute_keyboard([["Удалить"]])
```

`has_keyboard()` возвращает `bool`; assert/refute-варианты выбрасывают
`AssertionError` при невыполнении условия.

## Исключения

Все специальные исключения наследуются от `BotTesterError`:

| Исключение | Когда возникает |
|---|---|
| `NoBotMessageError` | действие требует предыдущего сообщения бота |
| `NoBotResponseError` | бот не отправил ответ на действие |
| `ButtonNotFoundError` | кнопка с указанным label не найдена |
| `AmbiguousButtonError` | найдено несколько кнопок с одинаковым label |
| `UrlButtonInteractionError` | предпринята попытка нажать URL-кнопку |
| `InvalidTranscriptError` | transcript для `chat()` имеет неверный формат |

Методы `assert_*` и `refute_*` используют стандартный `AssertionError`, чтобы
pytest показывал обычное падение проверки.

Исключения полезно знать для диагностики теста. Обычно не требуется отдельно
тестировать, что сама библиотека выбрасывает их: цель теста — проверять поведение
вашего бота.

## Полный пример: регистрация с FSM

Следующий бот запрашивает имя и пароль, сохраняет данные, завершает FSM и
подтверждает регистрацию.

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
    await message.answer("Как вас зовут?")


@dispatcher.message(Registration.name, F.text)
async def save_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)
    await state.set_state(Registration.confirmation)
    await message.answer(
        f"Сохранить имя {message.text}?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Продолжить",
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
    await callback.message.answer("Отправьте пароль.")


@dispatcher.message(Registration.password, F.text)
async def save_password(message: Message, state: FSMContext) -> None:
    await state.update_data(password=message.text)
    data = await state.get_data()
    await state.clear()
    await message.answer(f"Пользователь {data['name']} зарегистрирован.")


@pytest.mark.asyncio
async def test_registration_flow() -> None:
    tester = BotTester.from_dispatcher(dispatcher)

    response = await tester.start()
    response.assert_contains("Как вас зовут?")
    await tester.assert_state(Registration.name)

    response = await tester.send_message("Bob")
    response.assert_contains("Сохранить имя Bob?")
    response.assert_callback_button(
        "Продолжить",
        callback_data="continue",
    )
    await tester.assert_data(name="Bob")
    await tester.assert_state(Registration.confirmation)

    response = await tester.tap_button("Продолжить")
    response.assert_contains("Отправьте пароль.")
    await tester.assert_state(Registration.password)

    response = await tester.send_message("secret")
    response.assert_contains("Пользователь Bob зарегистрирован.")
    await tester.assert_state(None)
    await tester.refute_data(name="Bob")
    await tester.refute_data(password="secret")
```

После `state.clear()` и состояние FSM, и сохранённые данные удалены.

## Как структурировать тесты

Единственной «правильной» структуры нет. Выбирайте структуру, в которой легко
найти тест конкретного поведения. Например:

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

- `tests/unit/` проверяет бизнес-правила без Telegram и aiogram;
- `tests/flows/` проверяет хендлеры и пользовательские сценарии;
- `conftest.py` хранит общие fixture и fake-зависимости.

Пример fixture:

```python
import pytest

from aiogram_bot_tester import BotTester
from bot.routers.registration import router


@pytest.fixture
def tester() -> BotTester:
    return BotTester.from_routers(router)
```

Каждый тест получает новый `BotTester`, новый `Dispatcher` и новый
`MemoryStorage`. Это предотвращает перенос FSM state и data между тестами.
Роутеры глубоко копируются, поэтому fixture можно безопасно переиспользовать:

```python
@pytest.mark.asyncio
async def test_registration(tester: BotTester) -> None:
    response = await tester.start()
    response.assert_contains("Как вас зовут?")


@pytest.mark.asyncio
async def test_unexpected_message(tester: BotTester) -> None:
    response = await tester.send_message("???")
    response.assert_contains("Неизвестная команда")
```

## Практические рекомендации и ограничения

- Проверяйте пользовательское поведение, а не имя сработавшего хендлера.
- Для точного текста используйте `response.text`, для устойчивых сценариев —
  `assert_contains()` или `assert_matches()`.
- Проверяйте не только успешный путь, но и отмену, неверный ввод, повторные
  callback-запросы и fallback-хендлеры.
- Выделяйте вычислительную бизнес-логику в unit-тесты, когда это упрощает дизайн,
  но не откладывайте полезный flow-тест только ради «идеальной» архитектуры.
- Создавайте новый tester для каждого теста, чтобы изолировать FSM.
- Помните: методы взаимодействия возвращают последний ответ при нескольких
  `SendMessage`.
- `timeout` — дополнительное ожидание после обработки, а не дедлайн.
- `chat()` подходит только для линейных текстовых диалогов. Для кнопок, FSM и
  ветвлений используйте пошаговый API.
- Настоящий Telegram token и сетевое соединение для тестов не нужны.
