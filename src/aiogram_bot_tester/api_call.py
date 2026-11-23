"""Public snapshots of outgoing requests made by the bot."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Upload:
    filename: str | None
    url: str | None = None
    path: str | None = None


@dataclass(frozen=True, slots=True)
class ApiCall:
    method: str
    params: Mapping[str, object]
