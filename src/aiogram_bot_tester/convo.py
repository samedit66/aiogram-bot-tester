from __future__ import annotations

import dataclasses as dc
import re
from typing import Any

import aiogram.fsm.state as fsm_state


@dc.dataclass(frozen=True, slots=True)
class Command:
    command: str
    args: list[Any]
    prefix: str


@dc.dataclass(frozen=True, slots=True)
class Say:
    text: str


@dc.dataclass(frozen=True, slots=True)
class Tap:
    button: str


@dc.dataclass(frozen=True, slots=True)
class See:
    texts: list[str]


@dc.dataclass(frozen=True, slots=True)
class SeeRegex:
    regexes: list[str | re.Pattern]


@dc.dataclass(frozen=True, slots=True)
class SeeButton:
    button: str


@dc.dataclass(frozen=True, slots=True)
class InState:
    state: fsm_state.State | None


@dc.dataclass(frozen=True, slots=True)
class DataHas:
    kwargs: dict[str, Any]


Action = Command | Say | Tap | See | SeeRegex | SeeButton | InState | DataHas


@dc.dataclass(slots=True)
class Convo:
    """
    Represents a user interaction with a Telegram bot.
    This interaction consists of both user actions (like sending a text or tapping a button)
    and expectations about what the bot must answer back.
    """

    actions: list[Action] = dc.field(default_factory=list)
    """Action sequence consisting of user actions and expectations."""

    def command(self, command: str, *args: Any, prefix: str = "/") -> Convo:
        self.actions.append(Command(command, list(args), prefix))
        return self

    def say(self, text: str) -> Convo:
        self.actions.append(Say(text))
        return self

    def tap(self, button: str) -> Convo:
        self.actions.append(Tap(button))
        return self

    def see(self, *texts: str) -> Convo:
        self.actions.append(See(list(texts)))
        return self

    def see_regex(self, *regexes: str | re.Pattern) -> Convo:
        self.actions.append(SeeRegex(list(regexes)))
        return self

    def see_button(self, button: str) -> Convo:
        self.actions.append(SeeButton(button))
        return self

    def in_state(self, state: fsm_state.State | None) -> Convo:
        self.actions.append(InState(state))
        return self

    def data_has(self, **kwargs: Any) -> Convo:
        self.actions.append(DataHas(kwargs))
        return self
