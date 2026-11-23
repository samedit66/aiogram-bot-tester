import dataclasses as dc
import itertools
import re

from aiogram.types import Document, PhotoSize, Sticker, Video, Voice


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


@dc.dataclass(frozen=True, slots=True)
class BotMessage:
    """A message which the bot sends back."""

    text: str | None
    keyboard: list[list[Button]]
    caption: str | None = dc.field(default=None, kw_only=True)
    photo: tuple[PhotoSize, ...] = dc.field(default=(), kw_only=True)
    document: Document | None = dc.field(default=None, kw_only=True)
    voice: Voice | None = dc.field(default=None, kw_only=True)
    video: Video | None = dc.field(default=None, kw_only=True)
    sticker: Sticker | None = dc.field(default=None, kw_only=True)
    media_group_id: str | None = dc.field(default=None, kw_only=True)

    @property
    def buttons(self) -> list[Button]:
        """
        Flattens the attached keyboard into a flat list of buttons.

        Example:

        ```python
        keyboard = [
            [
                CallbackButton("Yes", data="yes"),
                CallbackButton("No", data="no"),
            ],
            [CallbackButton("Cancel", data="cancel")],
        ]
        message = BotMessage("Agree?", keyboard)
        print(message.buttons)  # A list of callback buttons
        ```
        """
        return list(itertools.chain.from_iterable(self.keyboard))

    def is_empty(self) -> bool:
        """
        Checks whether a message is empty.
        A message is empty when it has no text, keyboard, caption, or media.

        Example:

        ```python
        print(message.is_empty()) # True or False
        ```
        """
        return not any(
            (
                self.text,
                self.keyboard,
                self.caption,
                self.photo,
                self.document,
                self.voice,
                self.video,
                self.sticker,
            )
        )

    def assert_photo(self, *, file_id: str | None = None) -> None:
        """Assert that a photo is present and optionally match any of its file IDs."""
        if not self.photo:
            raise AssertionError("Expected a photo, but the message has no photo.")
        if file_id is not None and all(size.file_id != file_id for size in self.photo):
            actual = tuple(size.file_id for size in self.photo)
            raise AssertionError(f"Expected photo file_id {file_id!r}, got {actual!r}.")

    def assert_document(
        self, *, file_id: str | None = None, file_name: str | None = None
    ) -> None:
        """Assert that a document is present and match any supplied metadata."""
        _assert_attachment(
            "document", self.document, file_id=file_id, file_name=file_name
        )

    def assert_voice(self, *, file_id: str | None = None) -> None:
        """Assert that a voice message is present and optionally match its file ID."""
        _assert_attachment("voice", self.voice, file_id=file_id)

    def assert_video(self, *, file_id: str | None = None) -> None:
        """Assert that a video is present and optionally match its file ID."""
        _assert_attachment("video", self.video, file_id=file_id)

    def assert_sticker(
        self, *, file_id: str | None = None, emoji: str | None = None
    ) -> None:
        """Assert that a sticker is present and match any supplied metadata."""
        _assert_attachment("sticker", self.sticker, file_id=file_id, emoji=emoji)

    def assert_caption(self, expected: str | None) -> None:
        """Assert the exact caption, or its absence when expected is None."""
        if self.caption != expected:
            raise AssertionError(
                f"Expected caption {expected!r}, got {self.caption!r}."
            )

    def assert_caption_contains(self, text: str, *texts: str) -> None:
        """Assert that the caption contains at least one supplied substring."""
        expected = (text, *texts)
        if self.caption is None or not any(item in self.caption for item in expected):
            raise AssertionError(
                f"Expected caption to contain one of {expected!r}, got {self.caption!r}."
            )

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
        """
        Asserts that the message contains at least one of the specified texts.

        Example:

        ```python
        message.assert_contains("Hello", "Welcome")
        ```
        """
        expected = (text, *texts)
        if not self.contains(*expected):
            target = repr(text) if not texts else f"any of {expected!r}"
            raise AssertionError(
                f"Expected message to contain {target}, but got {self.text!r}."
            )

    def refute_contains(self, text: str, *texts: str) -> None:
        """
        Asserts that the message contains none of the specified texts.

        Example:

        ```python
        message.refute_contains("Error", "Failed")
        ```
        """
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
        """
        Asserts that the message matches at least one specified expression.
        Matching is backed by `re.search`.

        Example:

        ```python
        message.assert_matches(r"Order #\\d+", r"Request #\\d+")
        ```
        """
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
        """
        Asserts that the message matches none of the specified expressions.
        Matching is backed by `re.search`.

        Example:

        ```python
        message.refute_matches(r"error", r"failed")
        ```
        """
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
        """
        Asserts that the message has a button with the specified label.
        Reply, callback, and URL buttons are all considered.

        Example:

        ```python
        message.assert_button("Continue")
        ```
        """
        if not self.has_button(label):
            labels = [button.label for button in self.buttons]
            raise AssertionError(
                f"Expected message to have button {label!r}, "
                f"but available buttons were {labels!r}."
            )

    def refute_button(self, label: str) -> None:
        """
        Asserts that the message has no button with the specified label.
        Reply, callback, and URL buttons are all considered.

        Example:

        ```python
        message.refute_button("Cancel")
        ```
        """
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
        """
        Asserts that a URL button with the specified label and URL is attached.

        Example:

        ```python
        message.assert_url_button(
            "Open documentation",
            url="https://example.com/docs",
        )
        ```
        """
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
        """
        Asserts that a URL button with the specified label and URL is not attached.

        Example:

        ```python
        message.refute_url_button(
            "Delete account",
            url="https://example.com/delete",
        )
        ```
        """
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
        """
        Asserts that a callback button with the specified data is attached.
        Both the button label and callback data must match.

        Example:

        ```python
        message.assert_callback_button("Confirm", callback_data="confirm")
        ```
        """
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
        """
        Asserts that a callback button with the specified data is not attached.
        Both the button label and callback data must match.

        Example:

        ```python
        message.refute_callback_button("Cancel", callback_data="cancel")
        ```
        """
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
        """
        Asserts that the complete keyboard layout matches the expected layout.
        Button labels, rows, and ordering must match exactly.

        Example:

        ```python
        message.assert_keyboard([
            ["Yes", "No"],
            ["Cancel"],
        ])
        ```
        """
        actual = [[button.label for button in row] for row in self.keyboard]
        if not self.has_keyboard(keyboard):
            raise AssertionError(f"Expected keyboard {keyboard!r}, but got {actual!r}.")

    def refute_keyboard(self, keyboard: list[list[str]]) -> None:
        """
        Asserts that the complete keyboard layout differs from the given layout.

        Example:

        ```python
        message.refute_keyboard([
            ["Delete"],
            ["Cancel"],
        ])
        ```
        """
        if self.has_keyboard(keyboard):
            raise AssertionError(
                f"Expected keyboard not to equal {keyboard!r}, but it matched exactly."
            )


def _assert_attachment(
    kind: str,
    attachment: Document | Voice | Video | Sticker | None,
    **expected: str | None,
) -> None:
    if attachment is None:
        raise AssertionError(f"Expected {kind}, but the message has none.")
    for field, value in expected.items():
        if value is None:
            continue
        actual = getattr(attachment, field)
        if actual is None:
            raise AssertionError(
                f"Expected {kind} {field} {value!r}, but {field} is unavailable."
            )
        if actual != value:
            raise AssertionError(f"Expected {kind} {field} {value!r}, got {actual!r}.")
