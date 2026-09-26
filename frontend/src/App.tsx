import { FormEvent, useState } from "react";

type Message = {
  role: "user" | "assistant";
  content: string;
};

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");

  function sendMessage(event: FormEvent) {
    event.preventDefault();

    const content = draft.trim();
    if (!content) {
      return;
    }

    setMessages((currentMessages) => [
      ...currentMessages,
      { role: "user", content },
    ]);
    setDraft("");
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <button className="new-chat" type="button">
          + New chat
        </button>

        <nav aria-label="Chat sessions">
          <button className="session active" type="button">
            New chat
          </button>
        </nav>
      </aside>

      <section className="chat">
        <header className="chat-header">
          <div>
            <span className="eyebrow">AI CHAT</span>
            <h1>New chat</h1>
          </div>
        </header>

        <div className="messages">
          {messages.length === 0 ? (
            <div className="empty-state">
              <h2>How can I help?</h2>
              <p>Send a message to start a conversation.</p>
            </div>
          ) : (
            messages.map((message, index) => (
              <article
                className={`message ${message.role}`}
                key={`${message.role}-${index}`}
              >
                <div className="avatar">
                  {message.role === "user" ? "You" : "AI"}
                </div>
                <p>{message.content}</p>
              </article>
            ))
          )}
        </div>

        <form className="composer" onSubmit={sendMessage}>
          <textarea
            aria-label="Message"
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Message AI…"
            rows={1}
            value={draft}
          />
          <button disabled={!draft.trim()} type="submit">
            Send
          </button>
        </form>
      </section>
    </main>
  );
}