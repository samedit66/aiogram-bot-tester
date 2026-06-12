import dataclasses as dc
import itertools
import re


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
class BotMessage:
    """A message which the bot sends back."""

    text: str | None
    keyboard: list[list[Button]]

    @property
    def buttons(self) -> list[Button]:
        """
        Flattens the attached keyboard into a flat list of buttons.

        Example:

        ```python
        keyboard = [[CallbackButton("Yes"), CallbackButton("No")], [CallbackButton("Cancel")]]
        message = BotMessage("Agree?", keyboard)
        print(message.buttons()) # A list of callback buttons
        ```
        """
        return list(itertools.chain.from_iterable(self.keyboard))

    def is_empty(self) -> bool:
        """
        Checks whether a message is empty.
        A message is empty when it contains no text (`message_text` is `None`) and
        no keyboard (`attached_keyboard` is an empty `list`).

        Example:

        ```python
        print(message.is_empty()) # True or False
        ```
        """
        return not (self.text or self.keyboard)

    def contains_text(self, *texts: str) -> bool:
        """
        Checks whether a message contains any of the specified `texts`.
        Returns `True` if it does, `False` otherwise.

        Example:

        ```python
        # "Hello, World!" is the message text
        print(message.contains_text("Hi", "Hello")) # True
        ```
        """
        return bool(self.text and any(text in self.text for text in texts))

    def search_regex(self, *patterns: str | re.Pattern[str]) -> bool:
        """
        Checks whether a message any of the specified `regexes`.
        Converts each `str`-pattern into a `re.Pattern` first.
        Returns `True` if it matches, `False` otherwise.
        Matching is backed by `re.search`.

        Example:

        ```python
        # "1234" is the message text
        print(message.search_regex(r"\\d+")) # True
        ```
        """
        return bool(
            self.text
            and any(
                pattern.search(self.text)
                for pattern in (
                    re.compile(pattern) if isinstance(pattern, str) else pattern
                    for pattern in patterns
                )
            )
        )

    def has_button(self, label: str) -> bool:
        """
        Checks whether a message has the specified button.
        Does not care about which kind of button it checks, reply or inline.

        Example:

        ```python
        print(message.has_button("Yes"))
        ```
        """
        return any(label == button.label for button in self.buttons)

    def has_url_button(self, label: str, url: str) -> bool:
        """
        Checks whether an inline button is attached with specified `label` and `url`.

        Example:

        ```python
        message.has_url_button("Google it!", url="google.com")
        ```
        """
        return any(
            label == button.label and url == button.url
            for button in self.buttons
            if isinstance(button, UrlButton)
        )

    def has_callback_button(self, label: str, callback_data: str) -> bool:
        """
        Checks whether an inline button is attached with specified `label` and `callback_data`.

        Example:

        ```python
        message.has_callback_button("Yes", callback_data="yes-button")
        ```
        """
        return any(
            label == button.label and callback_data == button.data
            for button in self.buttons
            if isinstance(button, CallbackButton)
        )

    def has_keyboard(self, keyboard: list[list[str]]) -> bool:
        """
        Checks whether a message has the specified keyboard.
        A keyboard is matrix of button names.
        Order of buttons and presence of them all matter.

        Example:

        ```python
        message = BotMessage("Agree?", [
            [CallbackButton("Yes"), CallbackButton("No")],
            [CallbackButton("Cancel")]
        ])
        print(message.has_keyboard([
            ["Yes", "No"],
            ["Cancel"]
        ]))
        ```
        """
        return keyboard == [[button.label for button in row] for row in self.keyboard]
