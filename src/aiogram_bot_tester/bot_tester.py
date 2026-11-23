from __future__ import annotations

import asyncio
import copy
import dataclasses as dc
import datetime as dt
import itertools
import unittest.mock as mock
from collections.abc import AsyncGenerator, Callable, Iterable, Mapping, Sequence
from typing import Any, TypeVar, cast

import aiogram as aio
import aiogram.fsm.context as fsm_context
import aiogram.fsm.state as fsm_state
import aiogram.fsm.storage.memory as fsm_memory
import aiogram.methods as aio_methods
import aiogram.types as aio_types
from aiogram.client.session.base import BaseSession
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types.update import UpdateTypeLookupError

import aiogram_bot_tester.exceptions as abt_exceptions
import aiogram_bot_tester.types as abt_types
from aiogram_bot_tester import _media


_TelegramResult = TypeVar("_TelegramResult")


class _OfflineSession(BaseSession):
    def __init__(
        self, capture: Callable[[aio.Bot, aio_methods.TelegramMethod[Any]], object]
    ) -> None:
        super().__init__()
        self._capture = capture

    async def make_request(
        self,
        bot: aio.Bot,
        method: aio_methods.TelegramMethod[_TelegramResult],
        timeout: int | None = None,
    ) -> _TelegramResult:
        return cast(_TelegramResult, self._capture(bot, method))

    async def close(self) -> None:
        pass

    def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        raise NotImplementedError(
            "Downloading file content is unsupported by BotTester."
        )


class BotConversation:
    """A conversation abstraction used to interact with a bot."""

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
        self.user = aio_types.User(id=user_id, is_bot=False, first_name=user_first_name)
        self._max_message_id = 0
        self._chats = {chat_id: aio_types.Chat(id=chat_id, type="private")}
        self._max_update_id = 0
        self._file_ids = itertools.count(1)
        self._album_ids = itertools.count(1)

        self.bot = aio.Bot(token, session=_OfflineSession(self._capture_request))

        self.bot_messages: list[abt_types.BotMessage] = []
        self.api_calls: list[aio_methods.TelegramMethod[Any]] = []
        self._messages: dict[tuple[int, int], aio_types.Message] = {}
        self._last_message: aio_types.Message
        self._dispatch_lock = asyncio.Lock()

    async def send_message(
        self, text: str, timeout: int | None = None
    ) -> abt_types.BotMessage:
        return await self.send_payload(f"message: {text!r}", timeout, text=text)

    def file_id(self, supplied: str | None) -> str:
        return supplied if supplied is not None else f"test-file-{next(self._file_ids)}"

    async def send_payload(
        self, description: str, timeout: int | None, **fields: object
    ) -> abt_types.BotMessage:
        responses = await self._feed_updates(
            map(self._message_update, (fields,)), timeout
        )
        if not responses:
            raise abt_exceptions.NoBotResponseError(
                f"Bot did not respond to {description}"
            )
        return responses[-1]

    async def send_album(
        self, items: Sequence[_media.AlbumItem], timeout: int | None
    ) -> tuple[abt_types.BotMessage, ...]:
        payloads = _media.album_payloads(items)
        group_id = self._next_album_id()
        return await self._feed_updates(
            (
                self._message_update({**fields, "media_group_id": group_id})
                for fields in payloads
            ),
            timeout,
        )

    def _message_update(self, fields: Mapping[str, object]) -> aio_types.Update:
        message = aio_types.Message.model_validate(
            {
                "message_id": self._next_message_id(),
                "date": dt.datetime.now(dt.timezone.utc),
                "chat": self._chats[self.chat_id],
                "from_user": self.user,
                **fields,
            }
        )
        return aio_types.Update(update_id=self._next_update_id(), message=message)

    def _next_album_id(self) -> str:
        return f"test-album-{next(self._album_ids)}"

    async def tap_callback_button(
        self, button: abt_types.CallbackButton, timeout: int | None = None
    ) -> abt_types.BotMessage:
        update_id = self._next_update_id()
        update = aio_types.Update(
            update_id=update_id,
            callback_query=aio_types.CallbackQuery(
                id=f"test-callback-query-{update_id}",
                from_user=self.user,
                chat_instance=f"test-chat-instance-{self._last_message.chat.id}",
                data=button.data,
                message=self._last_message,
            ),
        )
        responses = await self.feed_update(update, timeout)
        if not responses:
            raise abt_exceptions.NoBotResponseError(
                f"Bot did not respond to tapping the button: {button.label!r}"
            )
        return responses[-1]

    async def feed_update(
        self, update: aio_types.Update, timeout: int | None = None
    ) -> tuple[abt_types.BotMessage, ...]:
        return await self._feed_updates((update,), timeout)

    async def _feed_updates(
        self, updates: Iterable[aio_types.Update], timeout: int | None
    ) -> tuple[abt_types.BotMessage, ...]:
        async with self._dispatch_lock:
            before = len(self.bot_messages)
            for update in updates:
                # Rebind nested Telegram objects for aiogram shortcuts.
                bound = aio_types.Update.model_validate(
                    update.model_dump(), context={"bot": self.bot}
                )
                self._observe_update(bound)
                result = await self.dispatcher.feed_update(bot=self.bot, update=bound)
                if isinstance(result, aio_methods.TelegramMethod):
                    await self.bot(result)
            if timeout:
                await asyncio.sleep(timeout)
            return tuple(self.bot_messages[before:])

    def _observe_update(self, update: aio_types.Update) -> None:
        self._max_update_id = max(self._max_update_id, update.update_id)
        try:
            event = update.event
        except UpdateTypeLookupError:
            return
        message = event.message if isinstance(event, aio_types.CallbackQuery) else event
        if isinstance(message, aio_types.Message):
            self._chats[message.chat.id] = message.chat
            self._max_message_id = max(self._max_message_id, message.message_id)
            if isinstance(event, aio_types.CallbackQuery):
                self._messages.setdefault(
                    (message.chat.id, message.message_id), message
                )

    async def get_state(self) -> str | None:
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

    def _next_message_id(self) -> int:
        self._max_message_id += 1
        return self._max_message_id

    def _next_update_id(self) -> int:
        self._max_update_id += 1
        return self._max_update_id

    def _resolve_chat_id(self, chat_id: int | str | None) -> int:
        if isinstance(chat_id, int):
            return chat_id
        if isinstance(chat_id, str) and chat_id.removeprefix("-").isdecimal():
            return int(chat_id)
        if isinstance(chat_id, str):
            for chat in self._chats.values():
                if chat.username and f"@{chat.username}".lower() == chat_id.lower():
                    return chat.id
        return self.chat_id

    def _record_message(
        self,
        message: aio_types.Message,
        markup: aio_types.ReplyMarkupUnion | None,
    ) -> aio_types.Message:
        self._messages[message.chat.id, message.message_id] = message
        self._last_message = message
        self.bot_messages.append(
            abt_types.BotMessage(
                text=message.text,
                keyboard=_keyboard(markup),
                caption=message.caption,
                photo=tuple(message.photo or ()),
                document=message.document,
                voice=message.voice,
                video=message.video,
                sticker=message.sticker,
                media_group_id=message.media_group_id,
            )
        )
        return message

    def _capture_request(
        self,
        bot: aio.Bot,
        method: aio_methods.TelegramMethod[Any],
    ) -> aio_types.Message | list[aio_types.Message] | bool | mock.MagicMock:
        self.api_calls.append(method.model_copy())
        if isinstance(method, aio_methods.AnswerCallbackQuery):
            return True
        if isinstance(method, aio_methods.SendMessage):
            return self._send_response(
                bot,
                method.chat_id,
                method.reply_markup,
                method.message_thread_id,
                method.business_connection_id,
                text=method.text,
                entities=method.entities,
            )
        if isinstance(
            method,
            (
                aio_methods.SendPhoto,
                aio_methods.SendDocument,
                aio_methods.SendVoice,
                aio_methods.SendVideo,
                aio_methods.SendSticker,
            ),
        ):
            fields = self._outgoing_media(method)
            return self._send_response(
                bot,
                method.chat_id,
                method.reply_markup,
                method.message_thread_id,
                method.business_connection_id,
                **fields,
            )
        if isinstance(method, aio_methods.SendMediaGroup):
            items = [
                item
                for item in method.media
                if isinstance(
                    item,
                    (
                        aio_types.InputMediaPhoto,
                        aio_types.InputMediaVideo,
                        aio_types.InputMediaDocument,
                    ),
                )
            ]
            if len(items) == len(method.media):
                payloads = _media.album_payloads(items, self._outgoing_file_id)
                group_id = self._next_album_id()
                return [
                    self._send_response(
                        bot,
                        method.chat_id,
                        None,
                        method.message_thread_id,
                        method.business_connection_id,
                        media_group_id=group_id,
                        **fields,
                    )
                    for fields in payloads
                ]
        if isinstance(
            method, (aio_methods.EditMessageText, aio_methods.EditMessageReplyMarkup)
        ):
            if method.inline_message_id is not None:
                return True
            if method.chat_id is None or method.message_id is None:
                raise TelegramBadRequest(method, "chat_id and message_id are required")
            previous_message = self._messages.get(
                (self._resolve_chat_id(method.chat_id), method.message_id)
            )
            if previous_message is None:
                raise TelegramBadRequest(method, "message to edit not found")
            changes: dict[str, object] = {
                "reply_markup": method.reply_markup,
                "edit_date": dt.datetime.now(dt.timezone.utc),
            }
            if isinstance(method, aio_methods.EditMessageText):
                changes.update(text=method.text, entities=method.entities)
            return self._record_message(
                previous_message.model_copy(update=changes), method.reply_markup
            )
        return mock.MagicMock()

    def _outgoing_file_id(self, source: str | aio_types.InputFile) -> str:
        return self.file_id(
            source if isinstance(source, str) and "://" not in source else None
        )

    def _outgoing_media(
        self,
        method: aio_methods.SendPhoto
        | aio_methods.SendDocument
        | aio_methods.SendVoice
        | aio_methods.SendVideo
        | aio_methods.SendSticker,
    ) -> dict[str, object]:
        if isinstance(method, aio_methods.SendSticker):
            return {
                "sticker": _media.sticker(
                    self._outgoing_file_id(method.sticker), method.emoji
                )
            }

        fields: dict[str, object] = {
            "caption": method.caption,
            "caption_entities": method.caption_entities,
        }
        if isinstance(method, aio_methods.SendPhoto):
            fields["photo"] = _media.photo(self._outgoing_file_id(method.photo))
        elif isinstance(method, aio_methods.SendDocument):
            name = (
                method.document.filename
                if isinstance(method.document, aio_types.InputFile)
                else None
            )
            fields["document"] = _media.document(
                self._outgoing_file_id(method.document), name
            )
        elif isinstance(method, aio_methods.SendVoice):
            fields["voice"] = _media.voice(
                self._outgoing_file_id(method.voice), method.duration or 0
            )
        else:
            fields["video"] = _media.video(
                self._outgoing_file_id(method.video),
                method.width or 640,
                method.height or 480,
                method.duration or 0,
            )
        return fields

    def _send_response(
        self,
        bot: aio.Bot,
        target: int | str | None,
        markup: aio_types.ReplyMarkupUnion | None,
        thread_id: int | None,
        business_connection_id: str | None,
        **fields: object,
    ) -> aio_types.Message:
        chat_id = self._resolve_chat_id(target)
        chat = self._chats.get(chat_id)
        if chat is None:
            chat = aio_types.Chat(
                id=chat_id, type="private" if chat_id > 0 else "supergroup"
            )
        message = aio_types.Message.model_validate(
            {
                "message_id": self._next_message_id(),
                "date": dt.datetime.now(dt.timezone.utc),
                "chat": chat,
                "from_user": aio_types.User(
                    id=bot.id, is_bot=True, first_name="Test Bot"
                ),
                "message_thread_id": thread_id,
                "business_connection_id": business_connection_id,
                "reply_markup": markup
                if isinstance(markup, aio_types.InlineKeyboardMarkup)
                else None,
                **fields,
            },
            context={"bot": bot},
        )
        return self._record_message(message, markup)


def _keyboard(
    markup: aio_types.ReplyMarkupUnion | None,
) -> list[list[abt_types.Button]]:
    if isinstance(markup, aio_types.InlineKeyboardMarkup):
        return [
            [_inline_button(button) for button in row] for row in markup.inline_keyboard
        ]
    if isinstance(markup, aio_types.ReplyKeyboardMarkup):
        return [
            [abt_types.Button(label=button.text) for button in row]
            for row in markup.keyboard
        ]
    return []


def _inline_button(button: aio_types.InlineKeyboardButton) -> abt_types.Button:
    if button.url is not None:
        return abt_types.UrlButton(label=button.text, url=button.url)
    if button.callback_data is not None:
        return abt_types.CallbackButton(label=button.text, data=button.callback_data)
    return abt_types.UnsupportedInlineButton(label=button.text)


@dc.dataclass(slots=True)
class BotTester:
    """A bot functionality tester."""

    bot_conversation: BotConversation

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
        bot_conversation = BotConversation(
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
    def api_calls(self) -> tuple[aio_methods.TelegramMethod[Any], ...]:
        """Return outgoing Telegram methods in call order, including failed calls."""
        return tuple(self.bot_conversation.api_calls)

    async def feed_update(
        self, update: aio_types.Update, *, timeout: int | None = None
    ) -> tuple[abt_types.BotMessage, ...]:
        """Dispatch an update and return its captured messages and edits in order.

        Execute any Telegram method returned by a handler as a webhook response.
        If given, `timeout` adds a wait in seconds after dispatching the update.
        """
        return await self.bot_conversation.feed_update(update, timeout)

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

    async def send_photo(
        self,
        *,
        file_id: str | None = None,
        width: int = 640,
        height: int = 480,
        caption: str | None = None,
        timeout: int | None = None,
    ) -> abt_types.BotMessage:
        """Simulate a photo and return the last captured response."""
        conversation = self.bot_conversation
        photo = _media.photo(conversation.file_id(file_id), width, height)
        return await conversation.send_payload(
            "photo", timeout, photo=photo, caption=caption
        )

    async def send_document(
        self,
        *,
        file_name: str,
        file_id: str | None = None,
        mime_type: str | None = None,
        caption: str | None = None,
        timeout: int | None = None,
    ) -> abt_types.BotMessage:
        """Simulate a document and return the last captured response."""
        conversation = self.bot_conversation
        document = _media.document(conversation.file_id(file_id), file_name, mime_type)
        return await conversation.send_payload(
            "document", timeout, document=document, caption=caption
        )

    async def send_voice(
        self,
        *,
        file_id: str | None = None,
        duration: int = 1,
        mime_type: str | None = None,
        caption: str | None = None,
        timeout: int | None = None,
    ) -> abt_types.BotMessage:
        """Simulate a voice message and return the last captured response."""
        conversation = self.bot_conversation
        voice = _media.voice(conversation.file_id(file_id), duration, mime_type)
        return await conversation.send_payload(
            "voice message", timeout, voice=voice, caption=caption
        )

    async def send_video(
        self,
        *,
        file_id: str | None = None,
        width: int = 640,
        height: int = 480,
        duration: int = 1,
        caption: str | None = None,
        timeout: int | None = None,
    ) -> abt_types.BotMessage:
        """Simulate a video and return the last captured response."""
        conversation = self.bot_conversation
        video = _media.video(conversation.file_id(file_id), width, height, duration)
        return await conversation.send_payload(
            "video", timeout, video=video, caption=caption
        )

    async def send_sticker(
        self,
        *,
        file_id: str | None = None,
        emoji: str | None = None,
        timeout: int | None = None,
    ) -> abt_types.BotMessage:
        """Simulate a static sticker and return the last captured response."""
        conversation = self.bot_conversation
        sticker = _media.sticker(conversation.file_id(file_id), emoji)
        return await conversation.send_payload("sticker", timeout, sticker=sticker)

    async def send_album(
        self, items: Sequence[_media.AlbumItem], *, timeout: int | None = None
    ) -> tuple[abt_types.BotMessage, ...]:
        """Deliver the album as separate updates and return all captured responses."""
        return await self.bot_conversation.send_album(items, timeout)

    async def send_command(
        self, command: str, *args: object, command_prefix: str = "/"
    ) -> abt_types.BotMessage:
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
                "BotMessage.assert_url_button(label, url=...)."
            )

        if isinstance(button, abt_types.UnsupportedInlineButton):
            raise abt_exceptions.UnsupportedButtonInteractionError(
                f"Inline button {label!r} does not send callback data and cannot be tapped."
            )
        if isinstance(button, abt_types.CallbackButton):
            return await self.bot_conversation.tap_callback_button(button, timeout)
        return await self.bot_conversation.send_message(label, timeout)

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
        return state == (await self.bot_conversation.get_state())

    async def data_has(self, **kwargs: Any) -> bool:
        """
        Checks whether the state context contains the specified `kwargs`.

        Example:

        ```python
        has_name = await tester.data_has(name="Bob")
        ```
        """
        data = await self.bot_conversation.get_data()
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
            actual = await self.bot_conversation.get_state()
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
            actual = await self.bot_conversation.get_data()
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
            actual = await self.bot_conversation.get_data()
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
