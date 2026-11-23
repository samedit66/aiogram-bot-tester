import dataclasses as dc


@dc.dataclass(frozen=True, slots=True)
class Button:
    label: str


@dc.dataclass(frozen=True, slots=True)
class CallbackButton(Button):
    data: str


@dc.dataclass(frozen=True, slots=True)
class UrlButton(Button):
    url: str


@dc.dataclass(frozen=True, slots=True)
class UnsupportedInlineButton(Button):
    pass
