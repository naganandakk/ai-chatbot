import React, { createContext, useContext, useState, useCallback } from "react";
import { ChatSession, SessionSummary } from "./api";

type NotificationVariant = "error" | "success";

interface AppNotification {
  id: string;
  message: string;
  variant: NotificationVariant;
}

type Setter<T> = React.Dispatch<React.SetStateAction<T>>;

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
  editTitleText: string;
  setEditTitleText: Setter<string>;
  inputMessage: string;
  setInputMessage: Setter<string>;
  promptFocusRequest: number;
  requestPromptFocus: () => void;
  notifications: AppNotification[];
  notifyError: (message: string) => void;
  notifySuccess: (message: string) => void;
  dismissNotification: (id: string) => void;
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
  const [editTitleText, setEditTitleText] = useState<string>('');
  const [inputMessage, setInputMessage] = useState<string>('');
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

  return (
    <Context.Provider value={{
      sidebarOpen, setSidebarOpen,
      activeSession, setActiveSession,
      isLoadingSession, setIsLoadingSession,
      sessions, setSessions,
      isGenerating, setIsGenerating,
      menuOpenId, setMenuOpenId,
      editingChatId, setEditingChatId,
      editTitleText, setEditTitleText,
      inputMessage, setInputMessage,
      promptFocusRequest, requestPromptFocus,
      notifications, notifyError, notifySuccess, dismissNotification
    }}>
      {children}
    </Context.Provider>
  );
};
