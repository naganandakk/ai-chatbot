export type Source = {
  title: string,
  url: string
};

// costUsd is null when the provider did not report a cost for the model
export type Usage = {
  inputTokens: number;
  outputTokens: number;
  costUsd: number | null;
};

// Totals across a session's replies. costUsd is null when no reply has a known cost, and
// unpricedMessages counts replies left out of the cost
export type SessionUsage = {
  inputTokens: number;
  outputTokens: number;
  costUsd: number | null;
  pricedMessages: number;
  unpricedMessages: number;
};

// id is empty for a file that is still only in the prompt, before the server has saved it
export type Attachment = {
  id: string;
  filename: string;
  mediaType: string;
  size: number;
};

export type AttachmentLimits = {
  maxFileBytes: number;
  maxFiles: number;
  maxTotalBytes: number;
  maxSessionBytes: number;
  acceptedExtensions: string[];
};

export type Message = {
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  sources: Source[];
  model: string;
  truncated?: boolean;
  usage?: Usage | null;
  durationMs?: number | null;
  attachments?: Attachment[];
};

export type SessionSummary = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
};

export type ChatSession = SessionSummary & {
  messages: Message[];
  usage: SessionUsage;
};

export type ModelOption = {
  id: string;
  name: string;
};

export type ModelList = {
  provider: string;
  models: ModelOption[];
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
  session: SessionSummary & { usage: SessionUsage };
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

export function attachmentUrl(attachmentId: string): string {
  return `/api/attachments/${attachmentId}`;
}

async function streamMessage(
  sessionId: string,
  message: string,
  model: string,
  files: File[],
  onDelta: (text: string) => void,
  onReset: () => void,
  onDone: (result: StreamDone) => void,
): Promise<void> {
  // Files need multipart, so the browser sets the Content-Type with its boundary
  const init: RequestInit = { method: "POST" };
  if (files.length > 0) {
    const form = new FormData();
    form.append("message", message);
    form.append("model", model);
    files.forEach((file) => form.append("files", file, file.name));
    init.body = form;
  } else {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify({ message, model });
  }

  const response = await fetch(`/api/sessions/${sessionId}/messages`, init);

  if (!response.ok) {
    // The server explains refusals such as an oversized upload in the body
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error ?? "Could not start the response stream");
  }

  if (!response.body) {
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

      if (event.startsWith("event: reset")) {
        onReset();
      } else if (event.startsWith("event: done")) {
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

  listModels: () =>
    request<ModelList>("/models"),

  getAttachmentLimits: () =>
    request<AttachmentLimits>("/attachment-limits"),

  streamMessage,
};