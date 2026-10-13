import json

import pytest

from backend.app import create_app
from core.chat_core.providers import TextDelta
from core.chat_core.service import ChatService
from core.chat_core.store import InMemorySessionStore
from core.chat_core.tools import checked_tools
from tests.support import USER_ID, sign_in


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def stream(self, *, model, messages, tools):
        self.calls.append({"tools": tools})
        yield TextDelta("Hi")

    def list_models(self):
        return []


def make_app(store, provider):
    service = ChatService(store=store, provider=provider)
    return create_app(store=store, chat_service=service)


def test_tools_endpoint_lists_web_search_for_the_ui():
    app = create_app(store=InMemorySessionStore())
    client = sign_in(app.test_client())

    response = client.get("/api/tools")

    assert response.status_code == 200
    assert response.get_json() == [
        {
            "id": "web_search",
            "name": "Web search",
            "description": "Search the web for current information and cite its sources.",
        }
    ]


def test_no_tools_are_sent_unless_the_message_asks_for_them():
    store = InMemorySessionStore()
    provider = FakeProvider()
    client = sign_in(make_app(store, provider).test_client())
    session = client.post("/api/sessions").get_json()

    client.post(f"/api/sessions/{session['id']}/messages", json={"message": "Hello"})

    assert provider.calls == [{"tools": []}]


def test_json_message_passes_the_selected_tools_to_the_provider():
    store = InMemorySessionStore()
    provider = FakeProvider()
    client = sign_in(make_app(store, provider).test_client())
    session = client.post("/api/sessions").get_json()

    client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"message": "Latest news", "tools": ["web_search"]},
    )

    assert provider.calls == [{"tools": ["web_search"]}]


def test_multipart_message_passes_the_selected_tools_to_the_provider():
    store = InMemorySessionStore()
    provider = FakeProvider()
    client = sign_in(make_app(store, provider).test_client())
    session = client.post("/api/sessions").get_json()

    client.post(
        f"/api/sessions/{session['id']}/messages",
        data={"message": "Latest news", "tools": ["web_search"]},
        content_type="multipart/form-data",
    )

    assert provider.calls == [{"tools": ["web_search"]}]


def test_unknown_tool_is_refused_before_the_message_is_saved():
    store = InMemorySessionStore()
    provider = FakeProvider()
    client = sign_in(make_app(store, provider).test_client())
    session = client.post("/api/sessions").get_json()

    body = client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"message": "Hello", "tools": ["calculator"]},
    ).get_data(as_text=True)

    event = json.loads(body.split("data: ", 1)[1].strip())
    assert "Unknown tool: calculator" in event["message"]
    assert provider.calls == []
    assert store.get(USER_ID, session["id"]).messages == []


def test_checked_tools_drops_repeats_and_keeps_order():
    assert checked_tools(["web_search", "web_search"]) == ["web_search"]
    assert checked_tools([]) == []


@pytest.mark.parametrize("names", ["web_search", ["web_search", 3], [None]])
def test_checked_tools_rejects_malformed_input(names):
    with pytest.raises(ValueError):
        checked_tools(names)
