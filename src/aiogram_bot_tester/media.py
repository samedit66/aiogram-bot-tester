"""Media metadata used by BotTester inputs and captured messages."""

from dataclasses import dataclass
from typing import TypeAlias


def _validate_file_id(file_id: str | None) -> None:
    if file_id is not None and (
        not isinstance(file_id, str) or not file_id.strip() or "://" in file_id
    ):
        raise ValueError("file_id must be a nonempty file identifier")


def _validate_dimensions(width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")


@dataclass(frozen=True, slots=True)
class CaptionEntity:
    type: str
    offset: int
    length: int
    url: str | None = None
    language: str | None = None
    custom_emoji_id: str | None = None


@dataclass(frozen=True, slots=True)
class Photo:
    file_id: str | None = None
    width: int = 640
    height: int = 480
    caption: str | None = None
    caption_entities: tuple[CaptionEntity, ...] = ()

    def __post_init__(self) -> None:
        _validate_file_id(self.file_id)
        _validate_dimensions(self.width, self.height)


@dataclass(frozen=True, slots=True)
class Document:
    file_name: str | None = None
    file_id: str | None = None
    mime_type: str | None = None
    caption: str | None = None
    caption_entities: tuple[CaptionEntity, ...] = ()

    def __post_init__(self) -> None:
        _validate_file_id(self.file_id)
        if self.file_name is not None and not self.file_name.strip():
            raise ValueError("file_name must not be empty")


@dataclass(frozen=True, slots=True)
class Voice:
    file_id: str | None = None
    duration: int = 1
    mime_type: str | None = None
    caption: str | None = None
    caption_entities: tuple[CaptionEntity, ...] = ()

    def __post_init__(self) -> None:
        _validate_file_id(self.file_id)
        if self.duration < 0:
            raise ValueError("duration must be nonnegative")


@dataclass(frozen=True, slots=True)
class Video:
    file_id: str | None = None
    width: int = 640
    height: int = 480
    duration: int = 1
    caption: str | None = None
    caption_entities: tuple[CaptionEntity, ...] = ()

    def __post_init__(self) -> None:
        _validate_file_id(self.file_id)
        _validate_dimensions(self.width, self.height)
        if self.duration < 0:
            raise ValueError("duration must be nonnegative")


@dataclass(frozen=True, slots=True)
class Sticker:
    file_id: str | None = None
    emoji: str | None = None

    def __post_init__(self) -> None:
        _validate_file_id(self.file_id)


AlbumItem: TypeAlias = Photo | Video | Document
Media: TypeAlias = AlbumItem | Voice | Sticker
