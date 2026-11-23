import asyncio
from datetime import datetime, timezone

import pytest
from aiogram import F, Router
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    Update,
    User,
)

from aiogram_bot_tester import (
    ApiCall,
    BotMessage,
    BotTester,
    CaptionEntity,
    Document,
    Photo,
    Sticker,
    Upload,
    Video,
    Voice,
)
from aiogram_bot_tester.exceptions import NoBotResponseError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "kwargs", "expected"),
    [
        ("photo", {"width": 80, "height": 60}, {"width": 80, "height": 60}),
        (
            "document",
            {"file_name": "orders.csv", "mime_type": "text/csv"},
            {"file_name": "orders.csv", "mime_type": "text/csv"},
        ),
        (
            "voice",
            {"duration": 0, "mime_type": "audio/ogg"},
            {"duration": 0, "mime_type": "audio/ogg"},
        ),
        (
            "video",
            {"width": 320, "height": 240, "duration": 3},
            {"width": 320, "height": 240, "duration": 3},
        ),
        (
            "sticker",
            {"emoji": "🙂"},
            {"emoji": "🙂", "type": "regular", "is_animated": False, "is_video": False},
        ),
    ],
)
async def test_incoming_media_uses_configured_conversation(kind, kwargs, expected):
    router = Router()

    @router.message(getattr(F, kind))
    async def handle(message: Message):
        assert message.chat.id == 20
        assert message.from_user is not None
        assert message.from_user.id == 21
        assert message.from_user.first_name == "Alice"
        assert message.caption == ("Input caption" if kind != "sticker" else None)
        attachment = getattr(message, kind)
        if kind == "photo":
            (attachment,) = attachment
        assert attachment.file_id == "incoming"
        assert attachment.file_unique_id
        for field, value in expected.items():
            assert getattr(attachment, field) == value
        await message.answer("First")
        await message.answer("Last")

    tester = BotTester.from_routers(
        router, chat_id=20, user_id=21, user_first_name="Alice"
    )
    if kind != "sticker":
        kwargs = {**kwargs, "caption": "Input caption"}
    response = await getattr(tester, f"send_{kind}")(file_id="incoming", **kwargs)
    response.assert_contains("Last")


@pytest.mark.asyncio
async def test_default_media_id_and_no_response():
    router = Router()
    ids = []

    @router.message(F.photo)
    async def handle(message: Message):
        assert message.photo is not None
        (photo,) = message.photo
        assert (photo.width, photo.height) == (640, 480)
        ids.append(photo.file_id)

    tester = BotTester.from_routers(router)
    for _ in range(2):
        with pytest.raises(NoBotResponseError, match="photo"):
            await tester.send_photo()
    assert len(set(ids)) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "kwargs"),
    [
        ("photo", {"width": 0}),
        ("document", {"file_name": " "}),
        ("voice", {"duration": -1}),
        ("video", {"height": -1}),
        ("sticker", {"file_id": ""}),
    ],
)
async def test_invalid_media_is_rejected_before_dispatch(kind, kwargs):
    router = Router()

    @router.message()
    async def handle():
        pytest.fail("invalid media was dispatched")

    tester = BotTester.from_routers(router)
    with pytest.raises(ValueError):
        await getattr(tester, f"send_{kind}")(**kwargs)


@pytest.mark.asyncio
async def test_album_dispatches_each_item_and_returns_all_responses():
    router = Router()
    received = []

    @router.message()
    async def handle(message: Message):
        received.append(message)
        if message.caption:
            await message.answer(message.caption)

    tester = BotTester.from_routers(router)
    items = [
        Photo(
            file_id="first",
            caption="One",
            caption_entities=(CaptionEntity(type="bold", offset=0, length=3),),
        ),
        Video(file_id="second", width=100, duration=0),
        Photo(file_id="third", caption="Three"),
    ]
    responses = await tester.send_album(items)
    assert tuple(response.text for response in responses) == ("One", "Three")
    assert received[0].photo[0].file_id == "first"
    (entity,) = received[0].caption_entities
    assert (entity.type, entity.offset, entity.length) == ("bold", 0, 3)
    assert received[1].video.file_id == "second"
    assert received[1].video.width == 100
    assert received[1].video.duration == 0
    assert received[2].photo[0].file_id == "third"
    assert received[0].media_group_id
    assert {message.media_group_id for message in received} == {
        received[0].media_group_id
    }
    assert len({message.message_id for message in received}) == 3
    assert await tester.send_album([Document(file_id="a"), Document(file_id="b")]) == ()
    assert received[-1].document.file_id == "b"
    assert received[-1].media_group_id != received[0].media_group_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "items",
    [
        [Photo(file_id="a")],
        [Photo(file_id="a")] * 11,
        [Photo(file_id="a"), Document(file_id="b")],
        [Photo(), Sticker()],
        [Photo(), InputMediaPhoto(media="foreign")],
    ],
)
async def test_invalid_album_is_rejected_before_first_update(items):
    router = Router()

    @router.message()
    async def handle():
        pytest.fail("invalid album was dispatched")

    with pytest.raises(ValueError):
        await BotTester.from_routers(router).send_album(items)


@pytest.mark.asyncio
async def test_album_waits_once_after_dispatch(monkeypatch):
    router = Router()
    items = [Photo(file_id="a"), Photo(file_id="b")]
    replies = []
    waits = []
    original_sleep = asyncio.sleep

    async def record_sleep(delay):
        waits.append(delay)
        await original_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", record_sleep)

    async def reply(message: Message):
        await message.answer("Album accepted")

    @router.message(F.photo)
    async def handle(message: Message):
        if message.photo[0].file_id == "b":
            replies.append(asyncio.create_task(reply(message)))

    tester = BotTester.from_routers(router)
    (response,) = await tester.send_album(items, timeout=1)
    response.assert_contains("Album accepted")
    assert replies[0].done()
    assert waits == [1]


@pytest.mark.asyncio
async def test_album_propagates_failure_and_keeps_completed_calls():
    items = [Photo(file_id="a"), Photo(file_id="b")]
    failing = Router()

    @failing.message(F.photo)
    async def fail_second(message: Message):
        if message.photo[0].file_id == "b":
            raise RuntimeError("second item failed")
        await message.answer("First accepted")

    tester = BotTester.from_routers(failing)
    with pytest.raises(RuntimeError, match="second item failed"):
        await tester.send_album([*items, Photo(file_id="c")])
    assert [call.params["text"] for call in tester.api_calls] == ["First accepted"]


@pytest.mark.asyncio
async def test_outgoing_media_assertions_and_metadata():
    router = Router()

    @router.message()
    async def respond(message: Message):
        photo = await message.answer_photo("photo-id", caption="Done today")
        assert isinstance(photo, Message)
        assert photo.photo[0].file_id == "photo-id"
        await message.answer_document(
            BufferedInputFile(b"contents", "report.pdf"), caption="Report"
        )
        await message.answer_voice("voice-id")
        await message.answer_video("video-id")
        await message.answer_sticker("sticker-id", emoji="🙂")
        await message.answer_sticker("other-sticker")
        await message.answer_document("document-id")

    tester = BotTester.from_routers(router)
    update = Update(
        update_id=1,
        message=Message(
            message_id=1,
            date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            chat=Chat(id=1, type="private"),
            from_user=User(id=1, is_bot=False, first_name="Test"),
            text="go",
        ),
    )
    (
        photo,
        document,
        voice,
        video,
        sticker,
        unknown_sticker,
        unknown_document,
    ) = await tester.feed_update(update)
    photo.assert_photo(file_id="photo-id")
    photo.assert_caption("Done today")
    photo.assert_caption_contains("missing", "today")
    document.assert_document(file_name="report.pdf")
    assert isinstance(document.document, Document)
    assert isinstance(photo.photo[0], Photo)
    assert isinstance(voice.voice, Voice)
    assert isinstance(video.video, Video)
    assert isinstance(sticker.sticker, Sticker)
    assert tester.api_calls[1].params["document"] == Upload(filename="report.pdf")
    voice.assert_voice(file_id="voice-id")
    voice.assert_caption(None)
    video.assert_video(file_id="video-id")
    sticker.assert_sticker(file_id="sticker-id", emoji="🙂")
    unknown_sticker.assert_sticker()
    unknown_document.assert_document(file_id="document-id")
    assert all(
        not response.is_empty() for response in (photo, document, voice, video, sticker)
    )

    with pytest.raises(AssertionError, match="photo file_id"):
        photo.assert_photo(file_id="wrong")
    with pytest.raises(AssertionError, match="caption"):
        photo.assert_caption("done today")
    with pytest.raises(AssertionError, match="caption"):
        photo.assert_caption_contains("missing")
    with pytest.raises(AssertionError, match="caption"):
        voice.assert_caption_contains("")
    for check, field, value in [
        (document.assert_document, "file_name", "wrong"),
        (voice.assert_voice, "file_id", "wrong"),
        (video.assert_video, "file_id", "wrong"),
        (sticker.assert_sticker, "emoji", "wrong"),
    ]:
        with pytest.raises(AssertionError, match=field):
            check(**{field: value})
    with pytest.raises(AssertionError, match="emoji is unavailable"):
        unknown_sticker.assert_sticker(emoji="🙂")
    with pytest.raises(AssertionError, match="file_name is unavailable"):
        unknown_document.assert_document(file_name="report.pdf")


def test_assert_photo_matches_any_size_and_assertions_reject_missing_media():
    sizes = tuple(Photo(file_id=str(n), width=n, height=n) for n in (32, 64))
    BotMessage(None, [], photo=sizes).assert_photo(file_id="32")
    text = BotMessage("Done", [])
    text.assert_caption(None)
    with pytest.raises(AssertionError, match="caption"):
        text.assert_caption("Done")
    for name in ("photo", "document", "voice", "video", "sticker"):
        with pytest.raises(AssertionError, match=name):
            getattr(text, f"assert_{name}")()


@pytest.mark.asyncio
async def test_media_response_preserves_keyboard_and_source_without_fetching():
    router = Router()
    url = "https://example.com/photo.jpg"

    @router.message()
    async def respond(message: Message):
        await message.answer_photo(
            url,
            caption="A photo",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Done", callback_data="done")]
                ]
            ),
        )

    @router.callback_query(F.data == "done")
    async def remove_keyboard(query: CallbackQuery):
        assert isinstance(query.message, Message)
        assert query.message.photo
        await query.message.edit_reply_markup(reply_markup=None)

    tester = BotTester.from_routers(router)
    response = await tester.send_message("go")
    response.assert_photo()
    response.assert_button("Done")
    call = tester.api_calls[0]
    assert isinstance(call, ApiCall)
    assert call.method == "sendPhoto"
    assert call.params["photo"] == url
    edited = await tester.tap_button("Done")
    edited.assert_photo()
    edited.assert_caption("A photo")
    edited.refute_button("Done")


@pytest.mark.asyncio
async def test_outgoing_album_captures_each_message_and_group_id():
    router = Router()

    @router.message(F.photo)
    async def respond(message: Message):
        sent = await message.answer_media_group(
            [
                InputMediaPhoto(media="photo-id", caption="Cover"),
                InputMediaVideo(media="video-id"),
            ]
        )
        assert len(sent) == 2
        assert sent[0].message_id != sent[1].message_id

    tester = BotTester.from_routers(router)
    first, second = await tester.send_album(
        [Photo(file_id="a", caption="begin"), Video(file_id="b")]
    )
    first.assert_photo(file_id="photo-id")
    first.assert_caption("Cover")
    second.assert_video(file_id="video-id")
    assert first.media_group_id and first.media_group_id == second.media_group_id


@pytest.mark.asyncio
async def test_request_snapshot_detaches_nested_telegram_models():
    router = Router()

    @router.message()
    async def respond(message: Message):
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Done", callback_data="done")]]
        )
        await message.answer("Ready", reply_markup=markup)
        markup.inline_keyboard[0].clear()

    tester = BotTester.from_routers(router)
    (await tester.start()).assert_button("Done")
    (call,) = tester.api_calls
    (row,) = call.params["reply_markup"]["inline_keyboard"]
    (button,) = row
    assert button["text"] == "Done"
    with pytest.raises(TypeError):
        button["text"] = "Changed"


@pytest.mark.asyncio
async def test_send_photo_accepts_caption_entities_as_keyword_argument():
    router = Router()

    @router.message(F.photo)
    async def handle(message: Message):
        (entity,) = message.caption_entities
        assert (entity.type, entity.offset, entity.length) == ("bold", 0, 5)
        await message.answer("Received")

    tester = BotTester.from_routers(router)
    reply = await tester.send_photo(
        caption="Hello",
        caption_entities=(CaptionEntity(type="bold", offset=0, length=5),),
    )
    reply.assert_contains("Received")
