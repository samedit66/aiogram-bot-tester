"""Construct offline Telegram media payloads."""

from collections.abc import Callable, Sequence
from typing import TypedDict

from aiogram import types

AlbumItem = types.InputMediaPhoto | types.InputMediaVideo | types.InputMediaDocument


class _FileFields(TypedDict):
    file_id: str
    file_unique_id: str


def _file_fields(file_id: str) -> _FileFields:
    if not file_id.strip():
        raise ValueError("file_id must not be empty")
    return {"file_id": file_id, "file_unique_id": f"unique-{file_id}"}


def photo(file_id: str, width: int = 640, height: int = 480) -> list[types.PhotoSize]:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    return [types.PhotoSize(width=width, height=height, **_file_fields(file_id))]


def document(
    file_id: str, file_name: str | None = None, mime_type: str | None = None
) -> types.Document:
    if file_name is not None and not file_name.strip():
        raise ValueError("file_name must not be empty")
    return types.Document(
        file_name=file_name, mime_type=mime_type, **_file_fields(file_id)
    )


def voice(file_id: str, duration: int = 1, mime_type: str | None = None) -> types.Voice:
    if duration < 0:
        raise ValueError("duration must be nonnegative")
    return types.Voice(duration=duration, mime_type=mime_type, **_file_fields(file_id))


def video(
    file_id: str, width: int = 640, height: int = 480, duration: int = 1
) -> types.Video:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if duration < 0:
        raise ValueError("duration must be nonnegative")
    return types.Video(
        width=width, height=height, duration=duration, **_file_fields(file_id)
    )


def sticker(file_id: str, emoji: str | None = None) -> types.Sticker:
    return types.Sticker(
        type="regular",
        width=512,
        height=512,
        is_animated=False,
        is_video=False,
        emoji=emoji,
        **_file_fields(file_id),
    )


def _album_file_id(source: str | types.InputFile) -> str:
    if not isinstance(source, str) or "://" in source.strip():
        raise ValueError("album media must be a file_id")
    return source


def album_payloads(
    items: Sequence[AlbumItem],
    resolve_file_id: Callable[[str | types.InputFile], str] = _album_file_id,
) -> list[dict[str, object]]:
    if not 2 <= len(items) <= 10:
        raise ValueError("an album requires 2 to 10 items")
    if any(isinstance(item, types.InputMediaDocument) for item in items) and not all(
        isinstance(item, types.InputMediaDocument) for item in items
    ):
        raise ValueError("documents must form a separate album")

    payloads = []
    for item in items:
        file_id = resolve_file_id(item.media)
        payload: dict[str, object] = {
            "caption": item.caption,
            "caption_entities": item.caption_entities,
        }
        if isinstance(item, types.InputMediaPhoto):
            payload["photo"] = photo(file_id)
        elif isinstance(item, types.InputMediaVideo):
            payload["video"] = video(
                file_id,
                item.width if item.width is not None else 640,
                item.height if item.height is not None else 480,
                item.duration if item.duration is not None else 1,
            )
        elif isinstance(item, types.InputMediaDocument):
            file_name = (
                item.media.filename if isinstance(item.media, types.InputFile) else None
            )
            payload["document"] = document(file_id, file_name)
        else:
            raise ValueError("albums support photos, videos, and documents")
        payloads.append(payload)
    return payloads
