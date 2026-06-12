import aiogram_bot_tester.types as abt_types


class BotTesterError(Exception):
    """Base exception for all bot testing errors."""


class NoBotMessageError(BotTesterError):
    """Operation requires an existing bot message."""


class NoBotResponseError(BotTesterError):
    """The bot did not produce any response to a user action."""


class ButtonNotFoundError(BotTesterError):
    def __init__(
        self,
        label: str,
        available_buttons: list[abt_types.Button],
    ) -> None:
        self.label = label
        self.available_buttons = available_buttons

        super().__init__(
            f"Button '{label}' not found. Available buttons: {available_buttons}"
        )


class UrlButtonInteractionError(BotTesterError):
    """URL buttons cannot be tapped in tests."""


class AmbiguousButtonError(BotTesterError):
    def __init__(
        self,
        label: str,
        available_buttons: list[abt_types.Button],
    ) -> None:
        self.label = label
        self.available_buttons = available_buttons

        super().__init__(
            f"There are several buttons named '{label}', cannot decide which one to tap. "
            f"Available buttons: {available_buttons}"
        )
