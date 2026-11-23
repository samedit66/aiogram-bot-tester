from __future__ import annotations

import asyncio
import datetime as dt
import itertools
import unittest.mock as mock
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import aiogram as aio
import aiogram.fsm.context as fsm_context
import aiogram.methods as aio_methods
import aiogram.types as aio_types
from aiogram.exceptions import TelegramBadRequest
from aiogram.types.update import UpdateTypeLookupError

from . import _telegram_media
from . import exceptions as abt_exceptions
from . import buttons
from .bot_message import BotMessage
from ._offline_session import _OfflineSession
from ._request_snapshot import snapshot
from .api_call import ApiCall
from .media import AlbumItem, Document, Media, Photo, Video


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

        self.bot_messages: list[BotMessage] = []
        self.api_calls: list[ApiCall] = []
        self._messages: dict[tuple[int, int], aio_types.Message] = {}
        self._last_message: aio_types.Message
        self._dispatch_lock = asyncio.Lock()

    async def send_message(self, text: str, timeout: int | None = None) -> BotMessage:
        return await self.send_payload(f"message: {text!r}", timeout, text=text)

    def file_id(self, supplied: str | None) -> str:
        return supplied if supplied is not None else f"test-file-{next(self._file_ids)}"

    async def send_payload(
        self, description: str, timeout: int | None, **fields: object
    ) -> BotMessage:
        responses = await self._feed_updates(
            map(self._message_update, (fields,)), timeout
        )
        if not responses:
            raise abt_exceptions.NoBotResponseError(
                f"Bot did not respond to {description}"
            )
        return responses[-1]

    async def send_media(self, media: Media, timeout: int | None) -> BotMessage:
        payload = _telegram_media.incoming_payload(media, self.file_id(media.file_id))
        return await self.send_payload(type(media).__name__.lower(), timeout, **payload)

    async def send_album(
        self, items: Sequence[AlbumItem], timeout: int | None
    ) -> tuple[BotMessage, ...]:
        _telegram_media.validate_album(items, Document)
        if any(not isinstance(item, (Photo, Video, Document)) for item in items):
            raise ValueError("albums support photos, videos, and documents")
        payloads = [
            _telegram_media.incoming_payload(item, self.file_id(item.file_id))
            for item in items
        ]
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
        self, button: buttons.CallbackButton, timeout: int | None = None
    ) -> BotMessage:
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
    ) -> tuple[BotMessage, ...]:
        return await self._feed_updates((update,), timeout)

    async def _feed_updates(
        self, updates: Iterable[aio_types.Update], timeout: int | None
    ) -> tuple[BotMessage, ...]:
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
            _telegram_media.capture_message(message, _keyboard(markup))
        )
        return message

    def _capture_request(
        self,
        bot: aio.Bot,
        method: aio_methods.TelegramMethod[Any],
    ) -> aio_types.Message | list[aio_types.Message] | bool | mock.MagicMock:
        self.api_calls.append(snapshot(method))
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
            fields = _telegram_media.outgoing_payload(method, self._outgoing_file_id)
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
                payloads = _telegram_media.outgoing_album_payloads(
                    items, self._outgoing_file_id
                )
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
) -> list[list[buttons.Button]]:
    if isinstance(markup, aio_types.InlineKeyboardMarkup):
        return [
            [_inline_button(button) for button in row] for row in markup.inline_keyboard
        ]
    if isinstance(markup, aio_types.ReplyKeyboardMarkup):
        return [
            [buttons.Button(label=button.text) for button in row]
            for row in markup.keyboard
        ]
    return []


def _inline_button(button: aio_types.InlineKeyboardButton) -> buttons.Button:
    if button.url is not None:
        return buttons.UrlButton(label=button.text, url=button.url)
    if button.callback_data is not None:
        return buttons.CallbackButton(label=button.text, data=button.callback_data)
    return buttons.UnsupportedInlineButton(label=button.text)
