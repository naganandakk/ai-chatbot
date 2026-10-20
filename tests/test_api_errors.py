from backend.app import create_app
from backend.app.sse import format_event
from core.chat_core.store import InMemorySessionStore
from tests.support import USER_ID, sign_in


class BrokenModelsService:
    def provider_name_for(self, user_id, requested):
        raise RuntimeError("database exploded")


def test_unknown_api_path_answers_with_json_404():
    client = sign_in(create_app().test_client())

    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.is_json
    assert "error" in response.get_json()


def test_wrong_method_answers_with_json_405():
    client = create_app().test_client()

    response = client.patch("/api/health")

    assert response.status_code == 405
    assert response.is_json
    assert "error" in response.get_json()


def test_unexpected_exception_answers_with_generic_json_500():
    app = create_app(chat_service=BrokenModelsService())
    client = sign_in(app.test_client())

    response = client.get("/api/models")

    assert response.status_code == 500
    assert response.get_json() == {"error": "Something went wrong. Please try again."}
    assert "database exploded" not in response.get_data(as_text=True)


def test_malformed_json_body_answers_with_json_400():
    client = sign_in(create_app().test_client())
    session = client.post("/api/sessions").get_json()

    response = client.put(
        f"/api/sessions/{session['id']}",
        data="{not json",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.is_json
    assert "error" in response.get_json()


def test_rename_requires_a_title():
    client = sign_in(create_app().test_client())
    session = client.post("/api/sessions").get_json()

    response = client.put(f"/api/sessions/{session['id']}", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_rename_refuses_blank_and_overlong_titles():
    client = sign_in(create_app().test_client())
    session = client.post("/api/sessions").get_json()

    blank = client.put(f"/api/sessions/{session['id']}", json={"title": "   "})
    overlong = client.put(f"/api/sessions/{session['id']}", json={"title": "x" * 201})

    assert blank.get_json() == {"error": "title cannot be empty"}
    assert overlong.status_code == 400
    assert overlong.get_json() == {"error": "title must be at most 200 characters"}


def test_rename_trims_the_title():
    client = sign_in(create_app().test_client())
    session = client.post("/api/sessions").get_json()

    response = client.put(f"/api/sessions/{session['id']}", json={"title": "  Trip plans  "})

    assert response.get_json()["title"] == "Trip plans"


def test_json_body_that_is_not_an_object_is_refused():
    client = sign_in(create_app().test_client())
    session = client.post("/api/sessions").get_json()

    response = client.put(f"/api/sessions/{session['id']}", json=["title"])

    assert response.status_code == 400
    assert response.get_json() == {"error": "Request body must be a JSON object"}


def test_message_tools_must_be_a_list_of_strings():
    store = InMemorySessionStore()
    app = create_app(store=store)
    client = sign_in(app.test_client())
    session = client.post("/api/sessions").get_json()

    response = client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"message": "hi", "tools": "web_search"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "tools must be a list of strings"}
    assert store.get(USER_ID, session["id"]).messages == []


def test_sse_frames_keep_the_event_and_data_layout():
    assert format_event("delta", {"text": "Hi"}) == 'event: delta\ndata: {"text": "Hi"}\n\n'
    assert format_event("reset", {}) == "event: reset\ndata: {}\n\n"
