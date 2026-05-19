from __future__ import annotations

import dataclasses as dc
import datetime as dt
import re
import typing as t
import unittest.mock as mock
from typing import ClassVar

import aiogram as aio
import aiogram.fsm.state as fsm_state
import aiogram.fsm.storage.memory as fsm_memory
import aiogram.methods as methods
import aiogram.types as types


@dc.dataclass(frozen=True, slots=True)
class InlineButton:
    """Snapshot of an inline keyboard button."""

    text: str
    """Visible label on the button."""

    callback_data: str | None
    """Callback payload attached to the button, or ``None`` if absent."""


@dc.dataclass(frozen=True, slots=True)
class CapturedMessage:
    """Snapshot of a message sent by the bot."""

    text: str | None
    """Message text, or ``None`` when the bot sent no text."""

    inline_keyboard: list[list[InlineButton]]
    """Inline keyboard layout captured from the message."""

    reply_keyboard: list[list[str]]
    """Reply keyboard layout captured from the message."""


@dc.dataclass(frozen=True, slots=True)
class Response:
    """Result of a synthetic interaction with the bot."""

    text: str | None
    """Bot text response, or ``None`` when the bot sent no text."""

    state: fsm_state.State | None
    """FSM state after handling the update, or ``None`` when inactive."""

    message: CapturedMessage | None
    """
    Captured outgoing message, if any.

    This includes the message text and any inline or reply keyboards.
    """

    def contains(self, text: str) -> bool:
        """Return ``True`` when the response text contains ``text``."""
        return self.text is not None and text in self.text

    def matches(self, regex: str | re.Pattern[str]) -> bool:
        """Return ``True`` when the response text matches ``regex``."""
        pattern = regex if isinstance(regex, re.Pattern) else re.compile(regex)
        return bool(pattern.match(self.text or ""))

    def has_inline_button(self, label: str) -> bool:
        """Return ``True`` when an inline button with ``label`` exists."""
        if self.message is None:
            return False

        return any(
            button.text == label
            for row in self.message.inline_keyboard
            for button in row
        )

    def has_reply_button(self, label: str) -> bool:
        """Return ``True`` when a reply button with ``label`` exists."""
        if self.message is None:
            return False

        return any(label in row for row in self.message.reply_keyboard)

    def has_inline_keyboard_like(
        self,
        keyboard: list[list[str]],
    ) -> bool:
        """Return ``True`` when the inline keyboard matches ``keyboard``."""
        if self.message is None:
            return False

        return [
            [button.text for button in row] for row in self.message.inline_keyboard
        ] == keyboard

    def has_reply_keyboard_like(
        self,
        keyboard: list[list[str]],
    ) -> bool:
        """Return ``True`` when the reply keyboard matches ``keyboard``."""
        if self.message is None:
            return False

        return self.message.reply_keyboard == keyboard

    def in_state(self, state: fsm_state.State) -> bool:
        """Return ``True`` when the response FSM state equals ``state``."""
        return self.state == state


@dc.dataclass(slots=True)
class BotTester:
    """Helper for driving a bot through synthetic updates in tests."""

    bot: aio.Bot
    """Attached bot instance."""

    dispatcher: aio.Dispatcher
    """Attached dispatcher instance."""

    messages: list[CapturedMessage] = dc.field(default_factory=list)
    """Captured outgoing messages in send order."""

    CHAT_ID: ClassVar[int] = 1
    """Synthetic chat identifier used for generated updates."""

    USER_ID: ClassVar[int] = 1
    """Synthetic user identifier used for generated updates."""

    def __post_init__(self) -> None:
        """Attach a mocked transport layer used for capturing bot responses."""
        self.bot.session.make_request = mock.AsyncMock(
            side_effect=self._capture_request,
        )

    @classmethod
    def from_routers(
        cls,
        *routers: aio.Router,
        token: str = "42:TEST",
    ) -> BotTester:
        """Create a tester instance with the provided routers registered."""
        bot = aio.Bot(token=token)

        dispatcher = aio.Dispatcher(storage=fsm_memory.MemoryStorage())
        dispatcher.include_routers(*routers)

        return cls(bot, dispatcher)

    async def send_message(
        self,
        text: str,
        **message_kwargs: t.Any,
    ) -> Response:
        """Send a synthetic message and return the resulting response snapshot."""
        message = self._create_message(
            text=text,
            **message_kwargs,
        )

        update = types.Update(
            update_id=1,
            message=message,
        )

        await self.dispatcher.feed_update(
            self.bot,
            update,
        )

        return await self._build_response()

    async def click_reply_button(
        self,
        text: str,
        **message_kwargs: t.Any,
    ) -> Response:
        """Simulate a reply-keyboard click by sending the button text."""
        return await self.send_message(
            text=text,
            **message_kwargs,
        )

    async def click_inline_button(
        self,
        label: str,
    ) -> Response:
        """Simulate clicking an inline button with the given label."""
        callback_data = self._find_callback_data(label)

        telegram_message = self._create_message(
            text=self.messages[-1].text or "",
        )

        callback_query = types.CallbackQuery(
            id="test-callback-query",
            from_user=telegram_message.from_user,
            chat_instance="test-chat-instance",
            data=callback_data,
            message=telegram_message,
            bot=self.bot,
        )

        update = types.Update(
            update_id=1,
            callback_query=callback_query,
        )

        await self.dispatcher.feed_update(
            self.bot,
            update,
        )

        return await self._build_response()

    def _find_callback_data(
        self,
        label: str,
    ) -> str:
        """Return callback data associated with the inline button label."""
        if not self.messages:
            raise ValueError("No messages available")

        for row in self.messages[-1].inline_keyboard:
            for button in row:
                if button.text == label:
                    if button.callback_data is None:
                        raise ValueError(
                            f"Inline button '{label}' has no callback_data"
                        )

                    return button.callback_data

        raise ValueError(f"Inline button '{label}' not found")

    def _create_message(
        self,
        text: str,
        **message_kwargs: t.Any,
    ) -> types.Message:
        """Create a synthetic Telegram message object."""
        return types.Message(
            message_id=1,
            date=dt.datetime.now(),
            chat=types.Chat(
                id=self.CHAT_ID,
                type="private",
            ),
            from_user=types.User(
                id=self.USER_ID,
                is_bot=False,
                first_name="Test",
            ),
            text=text,
            bot=self.bot,
            **message_kwargs,
        )

    async def _capture_request(
        self,
        bot: aio.Bot,
        method: t.Any,
        timeout: int | None = None,
    ) -> mock.MagicMock:
        """Capture outgoing bot requests for later inspection."""
        if isinstance(method, methods.SendMessage):
            self.messages.append(
                CapturedMessage(
                    text=method.text,
                    inline_keyboard=self._extract_inline_keyboard(
                        method.reply_markup,
                    ),
                    reply_keyboard=self._extract_reply_keyboard(
                        method.reply_markup,
                    ),
                )
            )

        return mock.MagicMock()

    def _extract_inline_keyboard(
        self,
        markup: t.Any,
    ) -> list[list[InlineButton]]:
        """Extract inline keyboard data from Telegram markup."""
        if not isinstance(markup, types.InlineKeyboardMarkup):
            return []

        return [
            [
                InlineButton(
                    text=button.text,
                    callback_data=button.callback_data,
                )
                for button in row
            ]
            for row in markup.inline_keyboard
        ]

    def _extract_reply_keyboard(
        self,
        markup: t.Any,
    ) -> list[list[str]]:
        """Extract reply keyboard data from Telegram markup."""
        if not isinstance(markup, types.ReplyKeyboardMarkup):
            return []

        return [[button.text for button in row] for row in markup.keyboard]

    async def _build_response(self) -> Response:
        """Build a response snapshot from captured bot state."""
        state = await self.dispatcher.fsm.get_context(
            bot=self.bot,
            chat_id=self.CHAT_ID,
            user_id=self.USER_ID,
        ).get_state()

        message = self.messages[-1] if self.messages else None

        return Response(
            text=message.text if message else None,
            state=state,
            message=message,
        )
