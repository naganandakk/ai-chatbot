import React, { useState, useCallback } from "react";
import { ChatSession, SessionSummary } from "./api";

interface AppErrorItem {
  id: string;
  message: string;
}

export const Context = React.createContext();
export const ContextProvider = ({ children }) => {
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
      activeSession,  setActiveSession,
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