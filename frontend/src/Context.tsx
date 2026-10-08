import React, { useState } from "react";
import { ChatSession, SessionSummary } from "./api";

export const Context = React.createContext();
export const ContextProvider = ({ children }) => {
	 const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
	 const [activeSession, setActiveSession] = useState<ChatSession | null>(null);
	 const [sessions, setSessions] = useState<SessionSummary[]>([]);
	 const [error, setError] = useState<string | null>(null);
	 const [isGenerating, setIsGenerating] = useState<boolean>(false);
	 const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
   const [editingChatId, setEditingChatId] = useState<string | null>(null);
   const [editTitleText, setEditTitleText] = useState<string>('');
   const [inputMessage, setInputMessage] = useState<string>('');

	return (
		<Context.Provider value={{
      sidebarOpen, setSidebarOpen,
      activeSession,  setActiveSession,
      sessions, setSessions,
      error, setError,
      isGenerating, setIsGenerating,
      menuOpenId, setMenuOpenId,
      editingChatId, setEditingChatId,
      editTitleText, setEditTitleText,
      inputMessage, setInputMessage
    }}>
			{children}
		</Context.Provider>
	);
};