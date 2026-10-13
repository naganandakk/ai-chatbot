import base64
import io
import json
from types import SimpleNamespace

import pytest

from backend.app import create_app
from core.chat_core.attachments import AttachmentLimits, UploadedFile
from core.chat_core.providers import AnthropicProvider, TextDelta
from core.chat_core.providers.openrouter_provider import _openrouter_message
from core.chat_core.service import ChatService
from core.chat_core.settings import Settings
from core.chat_core.store import InMemorySessionStore
from tests.support import USER_ID, sign_in

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def stream(self, *, model, messages, tools):
        self.calls.append({"messages": messages})
        yield TextDelta("Got it")


class FakeMessages:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return []


def make_service(store, provider=None, limits=None) -> ChatService:
    return ChatService(
        store,
        provider=provider or FakeProvider(),
        settings=Settings(provider="anthropic", api_key="test-key", model="test-model"),
        attachment_limits=limits,
    )


def drain(generator):
    chunks = []
    while True:
        try:
            chunks.append(next(generator))
        except StopIteration as finished:
            return chunks, finished.value


def test_files_reach_provider_as_blocks_before_the_text():
    store = InMemorySessionStore()
    provider = FakeProvider()
    service = make_service(store, provider)
    session = store.create(USER_ID)
    files = [UploadedFile("shot.png", PNG), UploadedFile("notes.txt", b"hello")]

    drain(service.stream_reply(USER_ID, session.id, "What is this?", files=files))

    content = provider.calls[0]["messages"][0]["content"]
    assert content[0] == {
        "type": "image",
        "filename": "shot.png",
        "media_type": "image/png",
        "data": PNG,
    }
    assert content[1] == {"type": "text", "text": '<file name="notes.txt">\nhello\n</file>'}
    assert content[2] == {"type": "text", "text": "What is this?"}


def test_attachment_only_message_is_allowed():
    store = InMemorySessionStore()
    provider = FakeProvider()
    service = make_service(store, provider)
    session = store.create(USER_ID)

    _, reply = drain(service.stream_reply(USER_ID, session.id, "  ", files=[UploadedFile("a.png", PNG)]))

    saved = store.get(USER_ID, session.id).messages[0]
    assert saved.content == ""
    assert len(saved.attachments) == 1
    assert reply.content == "Got it"
    assert provider.calls[0]["messages"][0]["content"][0]["type"] == "image"


def test_earlier_attachments_are_resent_on_later_turns():
    store = InMemorySessionStore()
    provider = FakeProvider()
    service = make_service(store, provider)
    session = store.create(USER_ID)
    drain(service.stream_reply(USER_ID, session.id, "Look", files=[UploadedFile("a.png", PNG)]))

    drain(service.stream_reply(USER_ID, session.id, "Again"))

    history = provider.calls[1]["messages"]
    assert history[0]["content"][0]["data"] == PNG
    assert history[1] == {"role": "assistant", "content": "Got it"}
    assert history[2] == {"role": "user", "content": "Again"}


def test_rejected_upload_saves_nothing():
    store = InMemorySessionStore()
    service = make_service(store)
    session = store.create(USER_ID)

    with pytest.raises(ValueError, match="not a supported file"):
        drain(service.stream_reply(USER_ID, session.id, "Hi", files=[UploadedFile("tool.exe", b"MZ")]))

    assert store.get(USER_ID, session.id).messages == []


def test_anthropic_provider_sends_base64_image_and_document_blocks():
    client = SimpleNamespace(messages=FakeMessages())
    provider = AnthropicProvider(api_key="test-key", client=client)
    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "filename": "a.png", "media_type": "image/png", "data": PNG},
            {"type": "document", "filename": "a.pdf", "media_type": "application/pdf", "data": b"%PDF"},
            {"type": "text", "text": "Hi"},
        ],
    }]

    list(provider.stream(model="m", messages=messages, tools=[]))

    content = client.messages.requests[0]["messages"][0]["content"]
    encoded = base64.b64encode(PNG).decode("ascii")
    assert content[0] == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": encoded},
    }
    assert content[1]["type"] == "document"
    assert content[1]["source"]["media_type"] == "application/pdf"
    assert content[2] == {"type": "text", "text": "Hi"}


def test_openrouter_converts_images_and_pdfs_to_data_urls():
    message = _openrouter_message({
        "role": "user",
        "content": [
            {"type": "image", "filename": "a.png", "media_type": "image/png", "data": PNG},
            {"type": "document", "filename": "a.pdf", "media_type": "application/pdf", "data": b"%PDF"},
            {"type": "text", "text": "Hi"},
        ],
    })

    image, document, text = message["content"]
    assert image["type"] == "image_url"
    assert image["image_url"]["url"].startswith("data:image/png;base64,")
    assert document == {
        "type": "file",
        "file": {
            "filename": "a.pdf",
            "file_data": "data:application/pdf;base64," + base64.b64encode(b"%PDF").decode(),
        },
    }
    assert text == {"type": "text", "text": "Hi"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("MAX_ATTACHMENT_MB", "1")
    monkeypatch.setenv("MAX_ATTACHMENTS_TOTAL_MB", "2")
    store = InMemorySessionStore()
    limits = AttachmentLimits.from_env()
    app = create_app(store=store, chat_service=make_service(store, limits=limits))
    return sign_in(app.test_client())


def upload(client, session_id, files, message="Hi"):
    return client.post(
        f"/api/sessions/{session_id}/messages",
        data={"message": message, "files": files},
        content_type="multipart/form-data",
    )


def events(response):
    frames = response.get_data(as_text=True).strip().split("\n\n")
    parsed = []
    for frame in frames:
        name, data = frame.split("\n", 1)
        parsed.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return parsed


def test_multipart_message_saves_attachments_and_streams_reply(client):
    session = client.post("/api/sessions").get_json()

    response = upload(client, session["id"], [(io.BytesIO(PNG), "shot.png")])

    assert response.status_code == 200
    done = next(data for name, data in events(response) if name == "done")
    assert done["message"]["content"] == "Got it"
    saved = client.get(f"/api/sessions/{session['id']}").get_json()["messages"][0]
    assert saved["attachments"][0]["filename"] == "shot.png"
    assert saved["attachments"][0]["mediaType"] == "image/png"


def test_oversized_file_returns_error_event_and_saves_nothing(client):
    session = client.post("/api/sessions").get_json()
    big = PNG + b"0" * (1024 * 1024)

    response = upload(client, session["id"], [(io.BytesIO(big), "big.png")])

    assert response.status_code == 200
    name, data = events(response)[-1]
    assert name == "error"
    assert data["message"] == "big.png is larger than 1 MB."
    assert client.get(f"/api/sessions/{session['id']}").get_json()["messages"] == []


def test_request_over_total_limit_returns_413_json(client):
    session = client.post("/api/sessions").get_json()
    huge = b"0" * (3 * 1024 * 1024)

    response = upload(client, session["id"], [(io.BytesIO(huge), "huge.txt")])

    assert response.status_code == 413
    assert "at most 2 MB" in response.get_json()["error"]


def test_attachment_is_served_with_its_media_type(client):
    session = client.post("/api/sessions").get_json()
    upload(client, session["id"], [(io.BytesIO(PNG), "shot.png")])
    attachment = client.get(f"/api/sessions/{session['id']}").get_json()["messages"][0]["attachments"][0]

    response = client.get(f"/api/attachments/{attachment['id']}")

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.data == PNG
    assert response.headers["Content-Disposition"].startswith("inline;")
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_non_image_attachment_downloads_instead_of_rendering(client):
    session = client.post("/api/sessions").get_json()
    upload(client, session["id"], [(io.BytesIO(b"%PDF-1.4 body"), "paper.pdf")])
    attachment = client.get(f"/api/sessions/{session['id']}").get_json()["messages"][0]["attachments"][0]

    response = client.get(f"/api/attachments/{attachment['id']}")

    assert response.headers["Content-Disposition"].startswith("attachment;")


def test_unknown_attachment_returns_404(client):
    response = client.get("/api/attachments/missing")

    assert response.status_code == 404


def test_limits_endpoint_reports_configured_values(client):
    limits = client.get("/api/attachment-limits").get_json()

    assert limits["maxFileBytes"] == 1024 * 1024
    assert limits["maxFiles"] == 5
    assert limits["maxTotalBytes"] == 2 * 1024 * 1024
    assert ".pdf" in limits["acceptedExtensions"]
