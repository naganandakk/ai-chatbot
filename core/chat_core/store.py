from .models import ChatMessage, ChatSession, utc_now


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}

    def create(self) -> ChatSession:
        session = ChatSession()
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> ChatSession | None:
        return self._sessions.get(session_id)

    def list(self) -> list[ChatSession]:
        return sorted(
            self._sessions.values(),
            key=lambda session: session.updated_at,
            reverse=True,
        )

    def add_message(self, session_id: str, role: str, content: str) -> ChatMessage:
        session = self._require(session_id)
        message = ChatMessage(role=role, content=content)
        session.messages.append(message)

        if role == "user" and session.title == "New chat":
            session.title = self._title_for(content)

        session.updated_at = utc_now()
        return message

    def clear(self, session_id: str) -> ChatSession:
        session = self._require(session_id)
        session.messages.clear()
        session.title = "New chat"
        session.updated_at = utc_now()
        return session

    def _require(self, session_id: str) -> ChatSession:
        session = self.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session

    @staticmethod
    def _title_for(content: str) -> str:
        normalized = content.strip().replace("\n", " ")
        return normalized[:48] or "New chat"