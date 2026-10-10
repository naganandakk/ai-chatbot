from abc import ABC, abstractmethod

from .models import ChatMessage, ChatSession, utc_now


class SessionStore(ABC):
    """Persistence contract for chat sessions.

    `list` returns summaries (no messages), newest first. Every method that takes a
    session ID raises `KeyError` when the session does not exist. Implementations must
    be safe to call from several threads at once.
    """

    @abstractmethod
    def create(self) -> ChatSession:
        ...

    @abstractmethod
    def get(self, session_id: str) -> ChatSession | None:
        ...

    @abstractmethod
    def list(self) -> list[ChatSession]:
        ...

    @abstractmethod
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: str = "",
        model: str = "",
        truncated: bool = False,
    ) -> ChatMessage:
        ...

    @abstractmethod
    def clear(self, session_id: str) -> ChatSession:
        ...

    @abstractmethod
    def delete(self, session_id: str) -> None:
        ...

    @abstractmethod
    def update(self, session_id: str, title: str) -> ChatSession:
        ...

    def close(self) -> None:
        # Stores without external resources need no cleanup.
        return None

    def _require(self, session_id: str) -> ChatSession:
        session = self.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session

    @staticmethod
    def _title_for(content: str) -> str:
        normalized = content.strip().replace("\n", " ")
        return normalized[:48] or "New chat"


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}

    def create(self) -> ChatSession:
        session = ChatSession()
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> ChatSession | None:
        return self._sessions.get(session_id)

    def list(self) -> list[ChatSession]:
        sessions = sorted(
            self._sessions.values(),
            key=lambda session: session.created_at,
            reverse=True,
        )
        return [
            ChatSession(
                id=session.id,
                title=session.title,
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
            for session in sessions
        ]

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: str = "",
        model: str = "",
        truncated: bool = False,
    ) -> ChatMessage:
        session = self._require(session_id)
        message = ChatMessage(
            role=role,
            content=content,
            sources=sources,
            model=model,
            truncated=truncated,
        )
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

    def delete(self, session_id: str) -> None:
        self._require(session_id)
        del self._sessions[session_id]

    def update(self, session_id: str, title: str) -> ChatSession:
        session = self._require(session_id)
        session.title = title
        session.updated_at = utc_now()
        return session
