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

    def contains(self, text: str, *texts: str) -> bool:
        """
        Checks whether a message contains any of the specified texts.
        Returns `True` if it does, `False` otherwise.

        Example:

        ```python
        # "Hello, World!" is the message text
        print(message.contains("Hi", "Hello")) # True
        ```
        """
        expected = (text, *texts)
        return bool(
            self.text is not None and any(item in self.text for item in expected)
        )

    def matches(
        self,
        pattern: str | re.Pattern[str],
        *patterns: str | re.Pattern[str],
    ) -> bool:
        """
        Checks whether the message matches any of the specified regular expressions.
        Converts each `str`-pattern into a `re.Pattern` first.
        Returns `True` if it matches, `False` otherwise.
        Matching is backed by `re.search`.

        Example:

        ```python
        # "1234" is the message text
        print(message.matches(r"\\d+")) # True
        ```
        """
        expected = (pattern, *patterns)
        return bool(
            self.text is not None
            and any(
                pattern.search(self.text)
                for pattern in (
                    re.compile(pattern) if isinstance(pattern, str) else pattern
                    for pattern in expected
                )
            )
        )

    def assert_contains(self, text: str, *texts: str) -> None:
        """Asserts that the message contains at least one of the specified texts."""
        expected = (text, *texts)
        if not self.contains(*expected):
            target = repr(text) if not texts else f"any of {expected!r}"
            raise AssertionError(
                f"Expected message to contain {target}, but got {self.text!r}."
            )

    def refute_contains(self, text: str, *texts: str) -> None:
        """Asserts that the message contains none of the specified texts."""
        expected = (text, *texts)
        if self.contains(*expected):
            found = tuple(
                item for item in expected if self.text is not None and item in self.text
            )
            target = repr(text) if not texts else f"any of {expected!r}"
            raise AssertionError(
                f"Expected message not to contain {target}, "
                f"but found {found!r} in {self.text!r}."
            )

    def assert_matches(
        self,
        pattern: str | re.Pattern[str],
        *patterns: str | re.Pattern[str],
    ) -> None:
        """Asserts that the message matches at least one specified expression."""
        expected = (pattern, *patterns)
        if not self.matches(*expected):
            target = repr(pattern) if not patterns else f"any of {expected!r}"
            raise AssertionError(
                f"Expected message to match {target}, but got {self.text!r}."
            )

    def refute_matches(
        self,
        pattern: str | re.Pattern[str],
        *patterns: str | re.Pattern[str],
    ) -> None:
        """Asserts that the message matches none of the specified expressions."""
        expected = (pattern, *patterns)
        matched = tuple(
            item
            for item in expected
            if self.text is not None and re.search(item, self.text)
        )
        if matched:
            target = repr(pattern) if not patterns else f"any of {expected!r}"
            raise AssertionError(
                f"Expected message not to match {target}, "
                f"but these patterns matched: {matched!r}. Actual text: {self.text!r}."
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

    def assert_button(self, label: str) -> None:
        """Asserts that the message has a button with the specified label."""
        if not self.has_button(label):
            labels = [button.label for button in self.buttons]
            raise AssertionError(
                f"Expected message to have button {label!r}, "
                f"but available buttons were {labels!r}."
            )

    def refute_button(self, label: str) -> None:
        """Asserts that the message has no button with the specified label."""
        if self.has_button(label):
            raise AssertionError(
                f"Expected message not to have button {label!r}, but it was present."
            )

    def has_url_button(self, label: str, *, url: str) -> bool:
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

    def assert_url_button(self, label: str, *, url: str) -> None:
        """Asserts that the specified URL button is attached."""
        if not self.has_url_button(label, url=url):
            available = [
                (button.label, button.url)
                for button in self.buttons
                if isinstance(button, UrlButton)
            ]
            raise AssertionError(
                f"Expected message to have URL button {label!r} with url={url!r}, "
                f"but available URL buttons were {available!r}."
            )

    def refute_url_button(self, label: str, *, url: str) -> None:
        """Asserts that the specified URL button is not attached."""
        if self.has_url_button(label, url=url):
            raise AssertionError(
                f"Expected message not to have URL button {label!r} with url={url!r}, "
                "but it was present."
            )

    def has_callback_button(self, label: str, *, callback_data: str) -> bool:
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

    def assert_callback_button(self, label: str, *, callback_data: str) -> None:
        """Asserts that the specified callback button is attached."""
        if not self.has_callback_button(label, callback_data=callback_data):
            available = [
                (button.label, button.data)
                for button in self.buttons
                if isinstance(button, CallbackButton)
            ]
            raise AssertionError(
                "Expected message to have callback button "
                f"{label!r} with callback_data={callback_data!r}, "
                f"but available callback buttons were {available!r}."
            )

    def refute_callback_button(self, label: str, *, callback_data: str) -> None:
        """Asserts that the specified callback button is not attached."""
        if self.has_callback_button(label, callback_data=callback_data):
            raise AssertionError(
                "Expected message not to have callback button "
                f"{label!r} with callback_data={callback_data!r}, but it was present."
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

    def assert_keyboard(self, keyboard: list[list[str]]) -> None:
        """Asserts that the complete keyboard layout matches the expected layout."""
        actual = [[button.label for button in row] for row in self.keyboard]
        if not self.has_keyboard(keyboard):
            raise AssertionError(f"Expected keyboard {keyboard!r}, but got {actual!r}.")

    def refute_keyboard(self, keyboard: list[list[str]]) -> None:
        """Asserts that the complete keyboard layout differs from the given layout."""
        if self.has_keyboard(keyboard):
            raise AssertionError(
                f"Expected keyboard not to equal {keyboard!r}, but it matched exactly."
            )
