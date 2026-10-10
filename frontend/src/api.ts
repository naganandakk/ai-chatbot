export type Source = {
  title: string,
  url: string
};

export type Message = {
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  sources: Source[];
  model: string;
  truncated?: boolean;
};

export type SessionSummary = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
};

export type ChatSession = SessionSummary & {
  messages: Message[];
};

export type ConfirmationMessage = {
  message: string
}

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`/api${path}`, options);

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error ?? "Request failed");
  }

  return response.json() as Promise<T>;
}

export type StreamDone = {
  message: Message;
  session: SessionSummary;
};

// Carries the server's copy of the session when the stream fails, so the UI can reconcile
export class StreamError extends Error {
  session: ChatSession | null;

  constructor(message: string, session: ChatSession | null) {
    super(message);
    this.name = "StreamError";
    this.session = session;
  }
}

async function streamMessage(
  sessionId: string,
  message: string,
  onDelta: (text: string) => void,
  onDone: (result: StreamDone) => void,
): Promise<void> {
  const response = await fetch(`/api/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok || !response.body) {
    throw new Error("Could not start the response stream");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";

  while (true) {
    const { done, value } = await reader.read();

    pending += decoder.decode(value ?? new Uint8Array(), {
      stream: !done,
    });

    const events = pending.split("\n\n");
    pending = events.pop() ?? "";

    for (const event of events) {
      const data = event
        .split("\n")
        .find((line) => line.startsWith("data: "))
        ?.slice(6);

      if (!data) {
        continue;
      }

      const payload = JSON.parse(data);

      if (event.startsWith("event: error")) {
        throw new StreamError(
          payload.message ?? "The response failed",
          payload.session ?? null,
        );
      }

      if (event.startsWith("event: done")) {
        onDone(payload as StreamDone);
      } else if (payload.text) {
        onDelta(payload.text);
      }
    }

    if (done) {
      return;
    }
  }
}

export const api = {
  createSession: () =>
    request<ChatSession>("/sessions", { method: "POST" }),

  getSession: (sessionId: string) =>
    request<ChatSession>(`/sessions/${sessionId}`),

  listSessions: () =>
    request<SessionSummary[]>("/sessions"),

  clearChatHistory: (sessionId: string) =>
    request<ChatSession>(`/sessions/${sessionId}/messages`, {
      method: "DELETE",
    }),

  deleteSession: (sessionId: string) =>
    request<ConfirmationMessage>(`/sessions/${sessionId}`, {
      method: "DELETE",
    }),

  renameSession: (sessionId: string, title: string) =>
    request<ChatSession>(`/sessions/${sessionId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ title }),
    }),

  streamMessage,
};