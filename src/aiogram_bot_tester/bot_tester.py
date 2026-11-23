from __future__ import annotations

import copy
import dataclasses as dc
from collections.abc import Mapping, Sequence
from typing import Any

import aiogram as aio
import aiogram.fsm.state as fsm_state
import aiogram.fsm.storage.memory as fsm_memory
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Update

from . import exceptions as abt_exceptions
from .bot_message import BotMessage
from .buttons import CallbackButton, UnsupportedInlineButton, UrlButton
from ._conversation import BotConversation as _BotConversation
from .api_call import ApiCall
from .media import AlbumItem, CaptionEntity, Document, Photo, Sticker, Video, Voice


@dc.dataclass(slots=True)
class BotTester:
    """A bot functionality tester."""

    _conversation: _BotConversation

    @classmethod
    def from_dispatcher(
        cls,
        dispatcher: aio.Dispatcher,
        *,
        token: str = "42:TEST",
        chat_id: int = 1,
        user_id: int = 1,
        user_first_name: str = "Test",
    ) -> BotTester:
        """Create a tester from an already configured dispatcher.

        Args:
            dispatcher: Configured aiogram dispatcher used to process test updates.
            token: Synthetic token used to identify the test bot.
            chat_id: ID of the simulated chat.
            user_id: ID of the simulated user.
            user_first_name: First name of the simulated user.

        Example:

        ```python
        from aiogram import Dispatcher
        from aiogram_bot_tester import BotTester

        dispatcher = Dispatcher()
        tester = BotTester.from_dispatcher(dispatcher)
        ```
        """
        bot_conversation = _BotConversation(
            dispatcher=dispatcher,
            token=token,
            chat_id=chat_id,
            user_id=user_id,
            user_first_name=user_first_name,
        )
        return cls(bot_conversation)

    @classmethod
    def from_routers(
        cls,
        *routers: aio.Router,
        dependencies: Mapping[str, Any] | None = None,
        middlewares: Sequence[BaseMiddleware] | None = None,
        token: str = "42:TEST",
        chat_id: int = 1,
        user_id: int = 1,
        user_first_name: str = "Test",
    ) -> BotTester:
        """Create a tester from routers with optional dependencies and middleware.

        Routers are deep-copied before they are attached to a new dispatcher, so
        the same router fixtures can be reused by multiple tests. Dependencies are
        added to aiogram's context data and injected into handlers by argument name.
        Middleware instances are not copied and are registered, in the given order,
        as inner middleware for both message and callback-query events.

        Args:
            *routers: Aiogram routers containing the handlers under test.
            dependencies: Named objects added to aiogram's context data and made
                available to handlers.
            middlewares: Middleware instances to apply to messages and callback
                queries. For other event types or outer middleware, configure a
                dispatcher directly and use :meth:`from_dispatcher`.
            token: Synthetic token used to identify the test bot.
            chat_id: ID of the simulated chat.
            user_id: ID of the simulated user.
            user_first_name: First name of the simulated user.

        Example:

        ```python
        from aiogram import Router
        from aiogram_bot_tester import BotTester

        router = Router()
        repository = object()
        tester = BotTester.from_routers(
            router,
            dependencies={"repository": repository},
        )
        ```
        """
        dispatcher = aio.Dispatcher(storage=fsm_memory.MemoryStorage())
        dispatcher.workflow_data.update(dependencies or {})

        for middleware in middlewares or []:
            dispatcher.message.middleware(middleware)
            dispatcher.callback_query.middleware(middleware)

        for router in routers:
            dispatcher.include_router(copy.deepcopy(router))
        return cls.from_dispatcher(
            dispatcher,
            token=token,
            chat_id=chat_id,
            user_id=user_id,
            user_first_name=user_first_name,
        )

    @property
    def api_calls(self) -> tuple[ApiCall, ...]:
        """Return outgoing Telegram methods in call order, including failed calls."""
        return tuple(self._conversation.api_calls)

    async def feed_update(
        self, update: Update, *, timeout: int | None = None
    ) -> tuple[BotMessage, ...]:
        """Dispatch an update and return its captured messages and edits in order.

        Execute any Telegram method returned by a handler as a webhook response.
        If given, `timeout` adds a wait in seconds after dispatching the update.
        """
        return await self._conversation.feed_update(update, timeout)

    async def send_message(
        self,
        text: str,
        timeout: int | None = None,
    ) -> BotMessage:
        """
        Sends a message to the bot.
        When the bot has not responded to the message, `NoBotResponseError` is raised.

        Example:

        ```python
        bot_message = await tester.send_message("/start")
        ```
        """
        return await self._conversation.send_message(text, timeout)

    async def send_photo(
        self,
        *,
        file_id: str | None = None,
        width: int = 640,
        height: int = 480,
        caption: str | None = None,
        caption_entities: tuple[CaptionEntity, ...] = (),
        timeout: int | None = None,
    ) -> BotMessage:
        """Simulate a photo and return the last captured response."""
        photo = Photo(
            file_id=file_id,
            width=width,
            height=height,
            caption=caption,
            caption_entities=caption_entities,
        )
        return await self._conversation.send_media(photo, timeout)

    async def send_document(
        self,
        *,
        file_name: str | None = None,
        file_id: str | None = None,
        mime_type: str | None = None,
        caption: str | None = None,
        caption_entities: tuple[CaptionEntity, ...] = (),
        timeout: int | None = None,
    ) -> BotMessage:
        """Simulate a document and return the last captured response."""
        document = Document(
            file_name=file_name,
            file_id=file_id,
            mime_type=mime_type,
            caption=caption,
            caption_entities=caption_entities,
        )
        return await self._conversation.send_media(document, timeout)

    async def send_voice(
        self,
        *,
        file_id: str | None = None,
        duration: int = 1,
        mime_type: str | None = None,
        caption: str | None = None,
        caption_entities: tuple[CaptionEntity, ...] = (),
        timeout: int | None = None,
    ) -> BotMessage:
        """Simulate a voice message and return the last captured response."""
        voice = Voice(
            file_id=file_id,
            duration=duration,
            mime_type=mime_type,
            caption=caption,
            caption_entities=caption_entities,
        )
        return await self._conversation.send_media(voice, timeout)

    async def send_video(
        self,
        *,
        file_id: str | None = None,
        width: int = 640,
        height: int = 480,
        duration: int = 1,
        caption: str | None = None,
        caption_entities: tuple[CaptionEntity, ...] = (),
        timeout: int | None = None,
    ) -> BotMessage:
        """Simulate a video and return the last captured response."""
        video = Video(
            file_id=file_id,
            width=width,
            height=height,
            duration=duration,
            caption=caption,
            caption_entities=caption_entities,
        )
        return await self._conversation.send_media(video, timeout)

    async def send_sticker(
        self,
        *,
        file_id: str | None = None,
        emoji: str | None = None,
        timeout: int | None = None,
    ) -> BotMessage:
        """Simulate a static sticker and return the last captured response."""
        return await self._conversation.send_media(
            Sticker(file_id=file_id, emoji=emoji), timeout
        )

    async def send_album(
        self, items: Sequence[AlbumItem], *, timeout: int | None = None
    ) -> tuple[BotMessage, ...]:
        """Deliver the album as separate updates and return all captured responses."""
        return await self._conversation.send_album(items, timeout)

    async def send_command(
        self, command: str, *args: object, command_prefix: str = "/"
    ) -> BotMessage:
        """
        Sends a command to the bot.
        Converts each of the given `args` to `str` first.
        Accepts a `command_prefix`, which defaults to `"/"`.
        Prefer to use this method instead of `send_message` if possible.

        Example:

        ```python
        message = await tester.send_command("sum", 1, 2)
        ```
        """
        command = f"{command_prefix}{command}"
        if args:
            command = f"{command} {' '.join(str(arg) for arg in args)}"
        return await self.send_message(command)

    async def start(self) -> BotMessage:
        """
        Sends a `"/start"` command to the bot.

        Example:

        ```python
        message = await tester.start()
        ```
        """
        return await self.send_command("start")

    async def tap_button(self, label: str, timeout: int | None = None) -> BotMessage:
        """
        Taps a button attached to the last sent by the bot message.
        Raises `NoBotMessageError` if the bot has not sent a message,
        `ButtonNotFoundError` if no button has the specified label,
        `AmbiguousButtonError` if multiple buttons have that label,
        `UrlButtonInteractionError` if the matching button opens a URL,
        or `UnsupportedButtonInteractionError` for other inline actions.

        Example:

        ```python
        message = await tester.tap_button("Click me")
        ```
        """
        if not self._conversation.bot_messages:
            raise abt_exceptions.NoBotMessageError(
                "Cannot tap a button because the bot has not sent any message yet."
            )

        last_bot_message = self._conversation.bot_messages[-1]
        buttons = [
            button for button in last_bot_message.buttons if label == button.label
        ]
        if not buttons:
            raise abt_exceptions.ButtonNotFoundError(label, last_bot_message.buttons)
        elif len(buttons) > 1:
            raise abt_exceptions.AmbiguousButtonError(label, last_bot_message.buttons)

        button = buttons[0]
        if isinstance(button, UrlButton):
            raise abt_exceptions.UrlButtonInteractionError(
                f"Button '{label}' is a URL button and cannot be tapped. "
                "Assert its existence using "
                "BotMessage.assert_url_button(label, url=...)."
            )

        if isinstance(button, UnsupportedInlineButton):
            raise abt_exceptions.UnsupportedButtonInteractionError(
                f"Inline button {label!r} does not send callback data and cannot be tapped."
            )
        if isinstance(button, CallbackButton):
            return await self._conversation.tap_callback_button(button, timeout)
        return await self._conversation.send_message(label, timeout)

    async def in_state(self, state: fsm_state.State | None) -> bool:
        """
        Checks whether the bot is in specified `state`.
        When `None` given, it means that the bot should not be in any state.

        Example:

        ```python
        from aiogram.fsm.state import State, StatesGroup

        class Form(StatesGroup):
            name = State()

        is_in_state = await tester.in_state(Form.name)
        ```
        """
        return state == (await self._conversation.get_state())

    async def data_has(self, **kwargs: Any) -> bool:
        """
        Checks whether the state context contains the specified `kwargs`.

        Example:

        ```python
        has_name = await tester.data_has(name="Bob")
        ```
        """
        data = await self._conversation.get_data()
        return all(key in data and data[key] == value for key, value in kwargs.items())

    async def assert_state(self, state: fsm_state.State | None) -> None:
        """
        Asserts that the bot is in the specified FSM state.
        Pass `None` to assert that no FSM state is active.

        Example:

        ```python
        from aiogram.fsm.state import State, StatesGroup

        class Form(StatesGroup):
            name = State()

        await tester.assert_state(Form.name)
        ```
        """
        if not await self.in_state(state):
            actual = await self._conversation.get_state()
            expected = state.state if state is not None else None
            raise AssertionError(
                f"Expected bot state to be {expected!r}, but current state was {actual!r}."
            )

    async def refute_state(self, state: fsm_state.State | None) -> None:
        """
        Asserts that the bot is not in the specified FSM state.
        Pass `None` to assert that an FSM state is active.

        Example:

        ```python
        from aiogram.fsm.state import State, StatesGroup

        class Form(StatesGroup):
            name = State()

        await tester.refute_state(Form.name)
        ```
        """
        if await self.in_state(state):
            expected = state.state if state is not None else None
            raise AssertionError(
                f"Expected bot state not to be {expected!r}, but it was active."
            )

    async def assert_data(self, **kwargs: Any) -> None:
        """
        Asserts that the FSM data contains all specified key-value pairs.
        Additional values stored in the FSM context are ignored.

        Example:

        ```python
        await tester.assert_data(name="Bob", age=30)
        ```
        """
        if not await self.data_has(**kwargs):
            actual = await self._conversation.get_data()
            raise AssertionError(
                f"Expected FSM data to contain {kwargs!r}, but current data was {actual!r}."
            )

    async def refute_data(self, **kwargs: Any) -> None:
        """
        Asserts that the FSM data does not contain all specified pairs.
        The assertion succeeds if at least one pair is absent or has another value.

        Example:

        ```python
        await tester.refute_data(name="Alice", age=30)
        ```
        """
        if await self.data_has(**kwargs):
            actual = await self._conversation.get_data()
            raise AssertionError(
                f"Expected FSM data not to contain {kwargs!r}, "
                f"but all specified values were present in {actual!r}."
            )

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
        Raises `InvalidTranscriptError` when the transcript is not well-formed.
        Raises `AssertionError` when the bot responds wrong.
        """
        blocks = transcript.strip().split("\n\n")
        for block in blocks:
            lines = [
                line.strip() for line in block.strip().splitlines() if line.strip()
            ]
            if len(lines) != 2:
                raise abt_exceptions.InvalidTranscriptError(
                    f"Each turn must have exactly 2 lines (User + Bot), got {len(lines)}"
                )

            user_line, bot_line = lines
            if not user_line.startswith("User:"):
                raise abt_exceptions.InvalidTranscriptError(
                    f"Expected line starting with 'User:', got: {user_line!r}"
                )
            if not bot_line.startswith("Bot:"):
                raise abt_exceptions.InvalidTranscriptError(
                    f"Expected line starting with 'Bot:', got: {bot_line!r}"
                )

            user_message = user_line[5:].strip()
            expected_bot_text = bot_line[4:].strip()

            response = await self.send_message(user_message)
            response.assert_contains(expected_bot_text)
