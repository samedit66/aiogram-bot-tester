"""Construct offline Telegram media payloads."""

from collections.abc import Callable, Sequence
from typing import TypedDict

from aiogram import methods, types

from .bot_message import BotMessage
from .buttons import Button
from .media import CaptionEntity, Document, Media, Photo, Sticker, Video, Voice

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


def outgoing_album_payloads(
    items: Sequence[AlbumItem],
    resolve_file_id: Callable[[str | types.InputFile], str],
) -> list[dict[str, object]]:
    validate_album(items, types.InputMediaDocument)

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


def incoming_payload(item: Media, file_id: str) -> dict[str, object]:
    if isinstance(item, Sticker):
        return {"sticker": sticker(file_id, item.emoji)}
    fields: dict[str, object] = {
        "caption": item.caption,
        "caption_entities": [
            types.MessageEntity(
                type=entity.type,
                offset=entity.offset,
                length=entity.length,
                url=entity.url,
                language=entity.language,
                custom_emoji_id=entity.custom_emoji_id,
            )
            for entity in item.caption_entities
        ]
        or None,
    }
    if isinstance(item, Photo):
        fields["photo"] = photo(file_id, item.width, item.height)
    elif isinstance(item, Document):
        fields["document"] = document(file_id, item.file_name, item.mime_type)
    elif isinstance(item, Voice):
        fields["voice"] = voice(file_id, item.duration, item.mime_type)
    elif isinstance(item, Video):
        fields["video"] = video(file_id, item.width, item.height, item.duration)
    return fields


def validate_album(items: Sequence[object], document_type: type[object]) -> None:
    if not 2 <= len(items) <= 10:
        raise ValueError("an album requires 2 to 10 items")
    documents = sum(isinstance(item, document_type) for item in items)
    if documents not in (0, len(items)):
        raise ValueError("documents must form a separate album")


def capture_message(message: types.Message, keyboard: list[list[Button]]) -> BotMessage:
    caption = message.caption
    entities = tuple(
        CaptionEntity(
            entity.type,
            entity.offset,
            entity.length,
            entity.url,
            entity.language,
            entity.custom_emoji_id,
        )
        for entity in message.caption_entities or ()
    )
    doc, sound, clip, icon = (
        message.document,
        message.voice,
        message.video,
        message.sticker,
    )
    return BotMessage(
        text=message.text,
        keyboard=keyboard,
        caption=caption,
        photo=tuple(
            Photo(item.file_id, item.width, item.height, caption, entities)
            for item in message.photo or ()
        ),
        document=Document(doc.file_name, doc.file_id, doc.mime_type, caption, entities)
        if doc is not None
        else None,
        voice=Voice(sound.file_id, sound.duration, sound.mime_type, caption, entities)
        if sound is not None
        else None,
        video=Video(
            clip.file_id, clip.width, clip.height, clip.duration, caption, entities
        )
        if clip is not None
        else None,
        sticker=Sticker(icon.file_id, icon.emoji) if icon is not None else None,
        media_group_id=message.media_group_id,
    )


def outgoing_payload(
    method: methods.SendPhoto
    | methods.SendDocument
    | methods.SendVoice
    | methods.SendVideo
    | methods.SendSticker,
    resolve_file_id: Callable[[str | types.InputFile], str],
) -> dict[str, object]:
    if isinstance(method, methods.SendSticker):
        return {"sticker": sticker(resolve_file_id(method.sticker), method.emoji)}

    fields: dict[str, object] = {
        "caption": method.caption,
        "caption_entities": method.caption_entities,
    }
    if isinstance(method, methods.SendPhoto):
        fields["photo"] = photo(resolve_file_id(method.photo))
    elif isinstance(method, methods.SendDocument):
        name = (
            method.document.filename
            if isinstance(method.document, types.InputFile)
            else None
        )
        fields["document"] = document(resolve_file_id(method.document), name)
    elif isinstance(method, methods.SendVoice):
        fields["voice"] = voice(resolve_file_id(method.voice), method.duration or 0)
    else:
        fields["video"] = video(
            resolve_file_id(method.video),
            method.width or 640,
            method.height or 480,
            method.duration or 0,
        )
    return fields
