import React, { createContext, useContext, useState, useCallback } from "react";
import { ChatSession, SessionSummary } from "./api";

interface AppErrorItem {
  id: string;
  message: string;
}

type Setter<T> = React.Dispatch<React.SetStateAction<T>>;

interface AppContextValue {
  sidebarOpen: boolean;
  setSidebarOpen: Setter<boolean>;
  activeSession: ChatSession | null;
  setActiveSession: Setter<ChatSession | null>;
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
  errors: AppErrorItem[];
  triggerError: (message: string) => void;
  removeError: (id: string) => void;
}

export const Context = createContext<AppContextValue | null>(null);

export const useAppContext = (): AppContextValue => {
  const value = useContext(Context);

  if (!value) {
    throw new Error("useAppContext must be used inside ContextProvider");
  }

  return value;
};

export const ContextProvider = ({ children }: { children: React.ReactNode }) => {
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
  const [activeSession, setActiveSession] = useState<ChatSession | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editTitleText, setEditTitleText] = useState<string>('');
  const [inputMessage, setInputMessage] = useState<string>('');
  const [errors, setErrors] = useState<AppErrorItem[]>([]);

  const removeError = useCallback((id: string) => {
    setErrors((prev) => prev.filter((err) => err.id !== id));
  }, []);

  const triggerError = useCallback((message: string) => {
    const id = crypto.randomUUID(); // Unique ID for every independent error

    setErrors((prev) => [...prev, { id, message }]);

    // Each specific error sets its own timer to clean itself up after 5 seconds
    setTimeout(() => {
      removeError(id);
    }, 5000);
  }, [removeError]);

  return (
    <Context.Provider value={{
      sidebarOpen, setSidebarOpen,
      activeSession, setActiveSession,
      sessions, setSessions,
      isGenerating, setIsGenerating,
      menuOpenId, setMenuOpenId,
      editingChatId, setEditingChatId,
      editTitleText, setEditTitleText,
      inputMessage, setInputMessage,
      errors, triggerError, removeError
    }}>
      {children}
    </Context.Provider>
  );
};
