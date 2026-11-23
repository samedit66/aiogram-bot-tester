from collections.abc import AsyncGenerator, Callable
from typing import Any, TypeVar, cast

import aiogram as aio
import aiogram.methods as aio_methods
from aiogram.client.session.base import BaseSession


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
