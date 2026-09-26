import { FormEvent, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { api, ChatSession, Message, SessionSummary } from "./api";

export default function App() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSession, setActiveSession] = useState<ChatSession | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

  async function refreshSessions() {
    try {
      setSessions(await api.listSessions());
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load sessions",
      );
    }
  }

  useEffect(() => {
    void refreshSessions();
  }, []);

  async function createSession() {
    if (isStreaming) {
      return;
    }

    try {
      setError("");
      const session = await api.createSession();
      setActiveSession(session);
      await refreshSessions();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not create a session",
      );
    }
  }

  async function openSession(sessionId: string) {
    if (isStreaming) {
      return;
    }

    try {
      setError("");
      setActiveSession(await api.getSession(sessionId));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not open the session",
      );
    }
  }

  async function clearSession() {
    if (!activeSession || isStreaming) {
      return;
    }

    try {
      setError("");
      setActiveSession(await api.clearSession(activeSession.id));
      await refreshSessions();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not clear the session",
      );
    }
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();

    const content = draft.trim();
    if (!content || isStreaming) {
      return;
    }

    try {
      setError("");

      let session = activeSession;
      if (!session) {
        session = await api.createSession();
      }

      const userMessage: Message = {
        role: "user",
        content,
        createdAt: new Date().toISOString(),
      };
      const assistantMessage: Message = {
        role: "assistant",
        content: "",
        createdAt: new Date().toISOString(),
      };

      setDraft("");
      setIsStreaming(true);
      setActiveSession({
        ...session,
        messages: [...session.messages, userMessage, assistantMessage],
      });

      await api.streamMessage(session.id, content, (chunk) => {
        setActiveSession((currentSession) => {
          if (!currentSession || currentSession.id !== session.id) {
            return currentSession;
          }

          const messages = [...currentSession.messages];
          const lastMessage = messages[messages.length - 1];

          messages[messages.length - 1] = {
            ...lastMessage,
            content: lastMessage.content + chunk,
          };

          return { ...currentSession, messages };
        });
      });

      setActiveSession(await api.getSession(session.id));
      await refreshSessions();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The assistant could not respond",
      );
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <button
          className="new-chat"
          disabled={isStreaming}
          onClick={() => void createSession()}
          type="button"
        >
          + New chat
        </button>

        <nav aria-label="Chat sessions">
          {sessions.map((session) => (
            <button
              className={
                activeSession?.id === session.id ? "session active" : "session"
              }
              disabled={isStreaming}
              key={session.id}
              onClick={() => void openSession(session.id)}
              type="button"
            >
              {session.title}
            </button>
          ))}
        </nav>
      </aside>

      <section className="chat">
        <header className="chat-header">
          <div>
            <span className="eyebrow">AI CHAT</span>
            <h1>{activeSession?.title ?? "Start a conversation"}</h1>
          </div>

          {activeSession && (
            <button
              className="clear"
              disabled={isStreaming}
              onClick={() => void clearSession()}
              type="button"
            >
              Clear chat
            </button>
          )}
        </header>

        <div className="messages">
          {!activeSession?.messages.length && (
            <div className="empty-state">
              <h2>How can I help?</h2>
              <p>Send a message to start a conversation.</p>
            </div>
          )}

          {activeSession?.messages.map((message, index) => (
            <article
              className={`message ${message.role}`}
              key={`${message.createdAt}-${index}`}
            >
              <div className="avatar">
                {message.role === "user" ? "You" : "AI"}
              </div>

              <div className="message-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content ||
                    (isStreaming &&
                    index === activeSession.messages.length - 1
                      ? "▍"
                      : "")}
                </ReactMarkdown>
              </div>
            </article>
          ))}
        </div>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <form className="composer" onSubmit={(event) => void sendMessage(event)}>
          <textarea
            aria-label="Message"
            disabled={isStreaming}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void sendMessage(event);
              }
            }}
            placeholder="Message AI…"
            rows={1}
            value={draft}
          />

          <button disabled={isStreaming || !draft.trim()} type="submit">
            {isStreaming ? "Thinking…" : "Send"}
          </button>
        </form>
      </section>
    </main>
  );
}