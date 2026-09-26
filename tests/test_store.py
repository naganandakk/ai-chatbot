from core.chat_core.store import SessionStore


def test_first_user_message_becomes_session_title():
    store = SessionStore()
    session = store.create()

    store.add_message(session.id, "user", "How do I build a chatbot?")

    saved_session = store.get(session.id)

    assert saved_session is not None
    assert saved_session.title == "How do I build a chatbot?"
    assert saved_session.messages[0].role == "user"
    assert saved_session.messages[0].content == "How do I build a chatbot?"


def test_clear_removes_messages_and_resets_title():
    store = SessionStore()
    session = store.create()

    store.add_message(session.id, "user", "A question")
    store.add_message(session.id, "assistant", "An answer")

    cleared_session = store.clear(session.id)

    assert cleared_session.messages == []
    assert cleared_session.title == "New chat"


def test_missing_session_raises_key_error():
    store = SessionStore()

    try:
        store.clear("missing-session")
    except KeyError as error:
        assert str(error) == "'Session not found: missing-session'"
    else:
        raise AssertionError("Expected KeyError")