from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.state import State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage
from aiogram.types import (
    CallbackQuery,
    Chat,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    Update,
    User,
)


@dataclass(slots=True)
class InlineButton:
    text: str
    callback_data: str | None


@dataclass(slots=True)
class CapturedMessage:
    text: str | None
    inline_keyboard: list[list[InlineButton]]
    reply_keyboard: list[list[str]]


@dataclass(slots=True)
class Response:
    text: str | None
    state: State | None
    message: CapturedMessage | None

    def contains(self, text: str) -> bool:
        if not self.message:
            return False

        return text in self.text

    def matches(self, regex: str | re.Pattern) -> bool:
        if not self.message:
            return False

        return re.compile(regex).match(self.text)

    def has_inline_button(self, label: str) -> bool:
        if not self.message:
            return False

        return any(
            button.text == label
            for row in self.message.inline_keyboard
            for button in row
        )

    def has_reply_button(self, label: str) -> bool:
        if not self.message:
            return False

        return any(label in row for row in self.message.reply_keyboard)

    def has_inline_keyboard_like(
        self,
        keyboard: list[list[str]],
    ) -> bool:
        if not self.message:
            return False

        return [
            [button.text for button in row] for row in self.message.inline_keyboard
        ] == keyboard

    def has_reply_keyboard_like(
        self,
        keyboard: list[list[str]],
    ) -> bool:
        if not self.message:
            return False

        return self.message.reply_keyboard == keyboard

    def in_state(self, state: State) -> bool:
        if not self.message:
            return False

        return self.state == state


class BotTester:
    CHAT_ID = 1
    USER_ID = 1

    def __init__(
        self,
        bot: Bot,
        dispatcher: Dispatcher,
    ):
        self.bot = bot
        self.dispatcher = dispatcher

        self.messages: list[CapturedMessage] = []

        self.bot.session.make_request = AsyncMock(
            side_effect=self._capture_request,
        )

    @classmethod
    def from_routers(
        cls,
        *routers: Router,
    ) -> BotTester:
        bot = Bot(token="42:TEST")

        dispatcher = Dispatcher(
            storage=MemoryStorage(),
        )

        dispatcher.include_routers(*routers)

        return cls(bot, dispatcher)

    async def send_message(
        self,
        text: str,
        **message_kwargs: Any,
    ) -> Response:
        message = self._create_message(
            text=text,
            **message_kwargs,
        )

        update = Update(
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
        **message_kwargs: Any,
    ) -> Response:
        return await self.send_message(
            text=text,
            **message_kwargs,
        )

    async def click_inline_button(
        self,
        label: str,
    ) -> Response:
        callback_data = self._find_callback_data(label)

        telegram_message = self._create_message(
            text=self.messages[-1].text or "",
        )

        callback_query = CallbackQuery(
            id="test-callback-query",
            from_user=telegram_message.from_user,
            chat_instance="test-chat-instance",
            data=callback_data,
            message=telegram_message,
            bot=self.bot,
        )

        update = Update(
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
        **message_kwargs: Any,
    ) -> Message:
        return Message(
            message_id=1,
            date=datetime.now(),
            chat=Chat(
                id=self.CHAT_ID,
                type="private",
            ),
            from_user=User(
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
        bot: Bot,
        method: Any,
        timeout: int | None = None,
    ) -> MagicMock:
        if isinstance(method, SendMessage):
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

        return MagicMock()

    def _extract_inline_keyboard(
        self,
        markup: Any,
    ) -> list[list[InlineButton]]:
        if not isinstance(markup, InlineKeyboardMarkup):
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
        markup: Any,
    ) -> list[list[str]]:
        if not isinstance(markup, ReplyKeyboardMarkup):
            return []

        return [[button.text for button in row] for row in markup.keyboard]

    async def _build_response(self) -> Response:
        state = await self.dispatcher.fsm.get_context(
            bot=self.bot, chat_id=self.CHAT_ID, user_id=self.USER_ID
        ).get_state()

        message = self.messages[-1] if self.messages else None

        return Response(
            text=message.text if message else None,
            state=state,
            message=message,
        )
