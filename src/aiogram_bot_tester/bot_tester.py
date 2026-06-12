from __future__ import annotations

import asyncio
import copy
import dataclasses as dc
import datetime as dt
import itertools
import unittest.mock as mock
from typing import Any, Iterator

import aiogram as aio
import aiogram.fsm.context as fsm_context
import aiogram.fsm.state as fsm_state
import aiogram.fsm.storage.memory as fsm_memory
import aiogram.methods as aio_methods
import aiogram.types as aio_types
from aiogram.client.session import aiohttp

import aiogram_bot_tester.exceptions as abt_exceptions
import aiogram_bot_tester.types as abt_types


def ids_generator(start: int = 1) -> Iterator[int]:
    yield from itertools.count(start)


class BotConversation:
    """A conversation asbtraction used to interact with a bot."""

    def __init__(
        self,
        dispatcher: aio.Dispatcher,
        token: str = "42:TEST",
        chat_id: int = 1,
        user_id: int = 1,
        user_first_name: str = "Test",
    ) -> None:
        self.dispatcher = dispatcher
        self.chat_id = chat_id
        self.user_id = user_id
        self.user_first_name = user_first_name
        self.message_ids = ids_generator()
        self.update_ids = ids_generator()

        mocked_session = aiohttp.AiohttpSession()
        mocked_session.make_request = mock.AsyncMock(side_effect=self._capture_request)
        self.bot = aio.Bot(token, session=mocked_session)

        self.bot_messages: list[abt_types.BotMessage] = []

    async def send_message(
        self,
        text: str,
        timeout: int | None = None,
    ) -> abt_types.BotMessage:
        """
        Send a message to the bot.
        Returns either a `BotMessage` or `None` when the bot has not answered in sendind
        a response back (usually happens when no handler was able to process the incoming message).
        A timeout may be set up to wait for the response.

        Example:

        ```python
        bot_message = await bot_conversation.send_message("/start")
        ```
        """
        before = len(self.bot_messages)
        await self.dispatcher.feed_update(
            bot=self.bot,
            update=aio_types.Update(
                update_id=next(self.message_ids),
                message=aio_types.Message(
                    message_id=next(self.update_ids),
                    date=dt.datetime.now(),
                    chat=aio_types.Chat(
                        id=self.chat_id,
                        type="private",
                    ),
                    from_user=aio_types.User(
                        id=self.user_id,
                        is_bot=False,
                        first_name=self.user_first_name,
                    ),
                    text=text,
                    bot=self.bot,
                ),
            ),
        )

        if timeout:
            await asyncio.sleep(timeout)

        if before == len(self.bot_messages):
            raise abt_exceptions.NoBotResponseError(
                f"Bot did not respond to message: {text!r}"
            )
        return self.bot_messages[-1]

    # We tap a button using its label, rather than its callback data,
    # because from the point of a user, they tap a button, not send a callback data
    async def tap_callback_button(
        self, label: str, timeout: int | None = None
    ) -> abt_types.BotMessage:
        """
        Tap an inline callback button.
        Raises `ValueError` when either there were no last message or no
        inline callback button with the given `label`.

        Example:

        ```python
        bot_message = await bot_conversation.tap_callback_button("Yes")
        ```
        """
        if not self.bot_messages:
            raise abt_exceptions.NoBotMessageError(
                "Cannot tap a button because the bot has not sent any message yet."
            )

        last_message = self.bot_messages[-1]
        callback_data = self._find_callback_data(label)
        if not callback_data:
            raise abt_exceptions.ButtonNotFoundError(label, last_message.buttons)

        before = len(self.bot_messages)
        message = self._create_message(last_message.text or "")
        await self.dispatcher.feed_update(
            bot=self.bot,
            update=aio_types.Update(
                update_id=next(self.update_ids),
                callback_query=aio_types.CallbackQuery(
                    id="test-callback-query",
                    from_user=message.from_user,
                    chat_instance="test-chat-instance",
                    data=callback_data,
                    message=message,
                    bot=self.bot,
                ),
            ),
        )

        if timeout:
            await asyncio.sleep(timeout)

        if before == len(self.bot_messages):
            raise abt_exceptions.NoBotResponseError(
                f"Bot did not respond to tapping the button: {label!r}"
            )
        return self.bot_messages[-1]

    async def get_state(self) -> fsm_state.State | None:
        """
        Get the current state of the bot.
        If the bot is not in any state, returns `None`.

        Example:

        ```python
        state = await bot_conversation.get_state()
        ```
        """
        return await self._get_fsm_context().get_state()

    async def get_data(self) -> dict[str, Any]:
        """
        Get the stored data of the bot.

        Example:

        ```python
        data = await bot_conversation.get_data()
        ```
        """
        return await self._get_fsm_context().get_data()

    def _get_fsm_context(self) -> fsm_context.FSMContext:
        return self.dispatcher.fsm.get_context(
            bot=self.bot,
            chat_id=self.chat_id,
            user_id=self.user_id,
        )

    def _find_callback_data(self, label: str) -> str | None:
        if not self.bot_messages:
            return None

        return next(
            (
                button.data
                for button in self.bot_messages[-1].buttons
                if isinstance(button, abt_types.CallbackButton)
                and button.label == label
            ),
            None,
        )

    def _create_message(self, text: str) -> aio_types.Message:
        return aio_types.Message(
            message_id=next(self.message_ids),
            date=dt.datetime.now(),
            chat=aio_types.Chat(
                id=self.chat_id,
                type="private",
            ),
            from_user=aio_types.User(
                id=self.user_id,
                is_bot=False,
                first_name="Test",
            ),
            text=text,
            bot=self.bot,
        )

    def _capture_request(
        self,
        bot: aio.Bot,
        method: aio_methods.TelegramMethod,
        timeout: int | None = None,
    ) -> mock.MagicMock:
        text = None
        keyboard = []
        if isinstance(method, aio_methods.SendMessage):
            text = method.text
            markup = method.reply_markup
            if isinstance(markup, aio_types.InlineKeyboardMarkup):
                keyboard = [
                    [
                        abt_types.UrlButton(label=button.text, url=button.url)
                        if button.url
                        else abt_types.CallbackButton(
                            label=button.text, data=button.callback_data
                        )
                        for button in row
                    ]
                    for row in markup.inline_keyboard
                ]
            elif isinstance(markup, aio_types.ReplyKeyboardMarkup):
                keyboard = [
                    [abt_types.Button(label=button.text) for button in row]
                    for row in markup.keyboard
                ]
        self.bot_messages.append(abt_types.BotMessage(text=text, keyboard=keyboard))
        return mock.MagicMock()


@dc.dataclass(slots=True)
class BotTester:
    """A bot functionality tester."""

    bot_conversation: BotConversation
    command_prefix: str = "/"

    @classmethod
    def from_dispatcher(cls, dispatcher: aio.Dispatcher, **kwargs: Any) -> BotTester:
        command_prefix = kwargs.pop("command_prefix", "/")
        bot_conversation = BotConversation(dispatcher=dispatcher, **kwargs)
        return cls(bot_conversation, command_prefix=command_prefix)

    @classmethod
    def from_routers(cls, *routers: aio.Router, **kwargs: Any) -> BotTester:
        dispatcher = aio.Dispatcher(storage=fsm_memory.MemoryStorage())

        # We perform deepcopy because of the fact, that a single router cannot
        # be attached to multiple dispatchers. This issues arises when a tester is
        # used in a fixture:
        # ```python
        # @pytest.fixture
        # def tester() -> BotTester:
        #    return BotTester.from_routers(router)
        #
        # @pytest.mark.asyncio
        # async def test_full_registration(tester: BotTester) -> None:
        #     ...
        #
        # @pytest.mark.asyncio
        # async def test_fallback(tester: BotTester) -> None:
        #     ...
        # ```
        # Without copying we get an error, because fixture gets called 2 times,
        # but in the first time the router was already attached
        dispatcher.include_routers(*[copy.deepcopy(router) for router in routers])
        return BotTester.from_dispatcher(dispatcher, **kwargs)

    async def send_message(
        self,
        text: str,
        timeout: int | None = None,
    ) -> abt_types.BotMessage:
        """
        Sends a message to the bot.
        When the bot has not responded to the message, `NoBotResponseError` is raised.

        Example:

        ```python
        bot_message = await tester.send_message("/start")
        ```
        """
        return await self.bot_conversation.send_message(text, timeout)

    async def send_command(
        self, command: str, *args: object, prefix: str = "/"
    ) -> abt_types.BotMessage:
        """
        Sends a command to the bot.
        Converts each of the given `args` to `str` first.
        Accepts a prefix for the command, which defaults to `"/"`.
        Prefer to use this method instead of `send_message` if possible.

        Example:

        ```python
        message = await tester.send_command("sum", 1, 2)
        ```
        """
        command = f"{prefix}{command}"
        if args:
            command = f"{command} {' '.join(str(arg) for arg in args)}"
        return await self.send_message(command)

    async def start(self) -> abt_types.BotMessage:
        """
        Sends a `"/start"` command to the bot.

        Example:

        ```python
        message = await tester.start()
        ```
        """
        return await self.send_command("start")

    async def tap_button(
        self, label: str, timeout: int | None = None
    ) -> abt_types.BotMessage:
        """
        Taps a button attached to the last sent by the bot message.
        If the button does not exist, raises `ValueError`.

        Example:

        ```python
        message = await tester.tap_button("Click me")
        ```
        """
        if not self.bot_conversation.bot_messages:
            raise abt_exceptions.NoBotMessageError(
                "Cannot tap a button because the bot has not sent any message yet."
            )

        last_bot_message = self.bot_conversation.bot_messages[-1]
        buttons = [
            button for button in last_bot_message.buttons if label == button.label
        ]
        if not buttons:
            raise abt_exceptions.ButtonNotFoundError(label, last_bot_message.buttons)
        elif len(buttons) > 1:
            raise abt_exceptions.AmbiguousButtonError(label, last_bot_message.buttons)

        button = buttons[0]
        if isinstance(button, abt_types.UrlButton):
            raise abt_exceptions.UrlButtonInteractionError(
                f"Button '{label}' is a URL button and cannot be tapped. "
                "Assert its existence using "
                "BotMessage.has_url_button(label, url)."
            )

        if isinstance(button, abt_types.CallbackButton):
            bot_message = await self.bot_conversation.tap_callback_button(
                label, timeout=timeout
            )
        else:  # reply button
            bot_message = await self.bot_conversation.send_message(
                text=label, timeout=timeout
            )
        return bot_message

    async def in_state(self, state: fsm_state.State | None) -> bool:
        """
        Checks whether the bot is in specified `state`.
        When `None` given, it means that the bot should not be in any state.

        Example:

        ```python
        class Form:
            name = State()

        message = await tester.in_state(Form.name)
        ```
        """
        return state == (await self.bot_conversation.get_state())

    async def data_has(self, **kwargs: Any) -> bool:
        """
        Checks whether the state context contains the specified `kwargs`.

        Example:

        ```python
        message = await tester.data_has(name="Bob")
        ```
        """
        data = await self.bot_conversation.get_data()
        return all(key in data and data[key] == value for key, value in kwargs.items())

    async def chat(self, transcript: str) -> None:
        """
        Plays a transcript. A form of declarative testing.

        Example:

        ```python
        await tester.chat(
            '''
            User: /start
            Bot: Hello! What's your name?

            User: Bob
            Bot: Hi, Bob!
            '''
        )
        ```

        Each user message if prefixed with `"User:"` and each bot message is prefixed with `"Bot:"`.
        Interactions are separated with an empty line.
        Raises `AssertionError` when the bot responds wrong.
        """

        raise NotImplementedError("This feature is currently being designed...")
