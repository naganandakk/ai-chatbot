import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { ChatSession, CurrentUser, SessionSummary, SIGNED_OUT_EVENT, api, restoreSession, sessionEvents } from "./api";
import { clearCache, readCache, writeCache, writeSessionCache } from "./cache";

export type AuthStatus = "loading" | "anonymous" | "authenticated";

type NotificationVariant = "error" | "success";

interface AppNotification {
  id: string;
  message: string;
  variant: NotificationVariant;
}

type Setter<T> = React.Dispatch<React.SetStateAction<T>>;

// Keeps the model the user last picked, so a page refresh reopens with it
const MODEL_STORAGE_KEY = "ai-chat.model";

function readStoredModel(): string {
  try {
    return window.localStorage.getItem(MODEL_STORAGE_KEY) ?? "";
  } catch {
    // Storage can be blocked, e.g. in some private browsing modes
    return "";
  }
}

// Keeps the tools the user switched on, so a page refresh keeps them. Tools start off.
const TOOLS_STORAGE_KEY = "ai-chat.tools";

function readStoredTools(): string[] {
  try {
    const stored = JSON.parse(window.localStorage.getItem(TOOLS_STORAGE_KEY) ?? "[]");
    return Array.isArray(stored) ? stored.filter((tool) => typeof tool === "string") : [];
  } catch {
    // Storage can be blocked, or hold something unreadable
    return [];
  }
}

type Theme = "light" | "dark";

// Keeps the theme the user picked, so a page refresh keeps it
const THEME_STORAGE_KEY = "ai-chat.theme";

// Until the user picks a theme, follow the OS setting
function readStoredTheme(): Theme {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark") {
      return stored;
    }
  } catch {
    // Storage can be blocked, e.g. in some private browsing modes
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

interface AppContextValue {
  sidebarOpen: boolean;
  setSidebarOpen: Setter<boolean>;
  activeSession: ChatSession | null;
  setActiveSession: Setter<ChatSession | null>;
  isLoadingSession: boolean;
  setIsLoadingSession: Setter<boolean>;
  sessions: SessionSummary[];
  setSessions: Setter<SessionSummary[]>;
  isGenerating: boolean;
  setIsGenerating: Setter<boolean>;
  menuOpenId: string | null;
  setMenuOpenId: Setter<string | null>;
  editingChatId: string | null;
  setEditingChatId: Setter<string | null>;
  inputMessage: string;
  setInputMessage: Setter<string>;
  selectedModel: string;
  selectModel: (modelId: string) => void;
  selectedTools: string[];
  selectTools: (toolIds: string[]) => void;
  theme: Theme;
  toggleTheme: () => void;
  promptFocusRequest: number;
  requestPromptFocus: () => void;
  notifications: AppNotification[];
  notifyError: (message: string) => void;
  notifySuccess: (message: string) => void;
  dismissNotification: (id: string) => void;
  authStatus: AuthStatus;
  currentUser: CurrentUser | null;
  signIn: (user: CurrentUser) => void;
  signOut: () => Promise<void>;
}

export const Context = createContext<AppContextValue | null>(null);

export const useAppContext = (): AppContextValue => {
  const value = useContext(Context);

  if (!value) {
    throw new Error("useAppContext must be used inside ContextProvider");
  }

  return value;
};

let notificationCounter = 0;

export const ContextProvider = ({ children }: { children: React.ReactNode }) => {
  // Open by default on desktop only, so the sidebar overlay doesn't cover the chat on phones
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(() => window.matchMedia('(min-width: 768px)').matches);
  const [activeSession, setActiveSession] = useState<ChatSession | null>(null);
  const [isLoadingSession, setIsLoadingSession] = useState<boolean>(false);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>(readStoredModel);
  const selectModel = useCallback((modelId: string) => {
    setSelectedModel(modelId);
    try {
      window.localStorage.setItem(MODEL_STORAGE_KEY, modelId);
    } catch {
      // The selection still applies for this page load if storage is unavailable
    }
  }, []);
  const [selectedTools, setSelectedTools] = useState<string[]>(readStoredTools);
  const selectTools = useCallback((toolIds: string[]) => {
    setSelectedTools(toolIds);
    try {
      window.localStorage.setItem(TOOLS_STORAGE_KEY, JSON.stringify(toolIds));
    } catch {
      // The selection still applies for this page load if storage is unavailable
    }
  }, []);
  const [theme, setTheme] = useState<Theme>(readStoredTheme);
  useEffect(() => {
    // Tailwind's `dark:` variants are keyed on the `dark` class on <html>
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  const toggleTheme = useCallback(() => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // The theme still applies for this page load if storage is unavailable
    }
  }, [theme]);
  // Bumped to focus the prompt even when it's already focus-worthy, e.g. clicking New Chat on an empty chat
  const [promptFocusRequest, setPromptFocusRequest] = useState<number>(0);
  const requestPromptFocus = useCallback(() => setPromptFocusRequest((count) => count + 1), []);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);

  const dismissNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((notification) => notification.id !== id));
  }, []);

  const pushNotification = useCallback((message: string, variant: NotificationVariant) => {
    // crypto.randomUUID is unavailable on plain-HTTP origins, so use a counter-based ID instead
    const id = `${Date.now()}-${++notificationCounter}`;

    setNotifications((prev) => [...prev, { id, message, variant }]);

    // Each notification sets its own timer to clean itself up after 5 seconds
    setTimeout(() => {
      dismissNotification(id);
    }, 5000);
  }, [dismissNotification]);

  const notifyError = useCallback((message: string) => pushNotification(message, "error"), [pushNotification]);
  const notifySuccess = useCallback((message: string) => pushNotification(message, "success"), [pushNotification]);

  const [authStatus, setAuthStatus] = useState<AuthStatus>("loading");
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);

  // Sign-out removes every cached value, so nothing from this account stays in the browser
  const clearSignedInState = useCallback(() => {
    clearCache();
    setCurrentUser(null);
    setAuthStatus("anonymous");
    setActiveSession(null);
    setSessions([]);
  }, []);

  // Shows the signed-in user's cached session list at once, while the sidebar asks the server for the current one
  const hydrateUser = useCallback((user: CurrentUser) => {
    // Values left by another account in this browser are removed, and this user's are kept
    clearCache(user.id);
    setSessions(readCache<SessionSummary[]>(user.id, "sessions")?.data ?? []);
    setCurrentUser(user);
    setAuthStatus("authenticated");
  }, []);

  // Saved in the same batch as the user, so the list is never written back empty for a signed-in user
  useEffect(() => {
    if (currentUser) {
      writeCache(currentUser.id, "sessions", sessions);
    }
  }, [sessions, currentUser]);

  // Streamed text changes the open chat on every chunk, so the chat is saved once the reply is done
  useEffect(() => {
    if (currentUser && activeSession && !isGenerating) {
      writeSessionCache(currentUser.id, activeSession);
    }
  }, [activeSession, isGenerating, currentUser]);

  useEffect(() => {
    let cancelled = false;

    restoreSession()
      .then((user) => {
        if (cancelled) {
          return;
        }
        if (user) {
          hydrateUser(user);
        } else {
          setCurrentUser(null);
          setAuthStatus("anonymous");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAuthStatus("anonymous");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    // The API client reports here when the session cannot be renewed
    const handleSignedOut = () => clearSignedInState();
    sessionEvents.addEventListener(SIGNED_OUT_EVENT, handleSignedOut);
    return () => sessionEvents.removeEventListener(SIGNED_OUT_EVENT, handleSignedOut);
  }, [clearSignedInState]);

  const signIn = useCallback((user: CurrentUser) => {
    hydrateUser(user);
  }, [hydrateUser]);

  const signOut = useCallback(async () => {
    try {
      await api.signOut();
    } catch {
      // Even if the server call fails, this browser should stop showing the account
    }
    clearSignedInState();
  }, [clearSignedInState]);

  return (
    <Context.Provider value={{
      sidebarOpen, setSidebarOpen,
      activeSession, setActiveSession,
      isLoadingSession, setIsLoadingSession,
      sessions, setSessions,
      isGenerating, setIsGenerating,
      menuOpenId, setMenuOpenId,
      editingChatId, setEditingChatId,
      inputMessage, setInputMessage,
      selectedModel, selectModel,
      selectedTools, selectTools,
      theme, toggleTheme,
      promptFocusRequest, requestPromptFocus,
      notifications, notifyError, notifySuccess, dismissNotification,
      authStatus, currentUser, signIn, signOut
    }}>
      {children}
    </Context.Provider>
  );
};
