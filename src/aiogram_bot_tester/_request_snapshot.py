"""Translate aiogram requests into public, provider-independent snapshots."""

from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType
from typing import Any

from aiogram.client.default import Default
from aiogram.methods import TelegramMethod
from aiogram.types import FSInputFile, InputFile, URLInputFile

from .api_call import ApiCall, Upload


def snapshot(method: TelegramMethod[Any]) -> ApiCall:
    params = method.model_dump(exclude_unset=True, warnings=False)
    return ApiCall(method.__api_method__, _mapping(params))


def _mapping(values: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType({key: _value(value) for key, value in values.items()})


def _value(value: object) -> object:
    if isinstance(value, InputFile):
        return Upload(
            filename=value.filename,
            url=value.url if isinstance(value, URLInputFile) else None,
            path=str(value.path) if isinstance(value, FSInputFile) else None,
        )
    if isinstance(value, Default):
        return None
    if isinstance(value, Enum):
        return _value(value.value)
    if value is None or isinstance(value, (str, int, float, bool, bytes)):
        return value
    if isinstance(value, dict):
        return _mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_value(item) for item in value)
    return repr(value)
