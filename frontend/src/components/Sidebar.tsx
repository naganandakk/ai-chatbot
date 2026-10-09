import React, { useRef, useEffect } from 'react';
import {
  Menu, SquarePen, MoreVertical, Edit2, Trash2, RotateCcw, Sparkles, Check, X
} from 'lucide-react';
import { api, ChatSession, SessionSummary } from "../api";
import { useAppContext } from "../Context";

const Sidebar = () => {
  const {
    sidebarOpen, setSidebarOpen,
    activeSession, setActiveSession,
    sessions, setSessions,
    triggerError,
    isGenerating, setIsGenerating,
    menuOpenId, setMenuOpenId,
    editingChatId, setEditingChatId,
    editTitleText, setEditTitleText
  } = useAppContext();
  const chatActionsRef = useRef<HTMLDivElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);

  async function refreshSessions () {
    try {
      const sessionList = await api.listSessions()
      setSessions(sessionList);
      if (sessionList.length > 0) {
        setActiveSession(await api.getSession(sessionList[0].id));
      }
    } catch (requestError) {
      triggerError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load sessions",
      );
    }
  }

  async function openSession(sessionId: string) {
    if (isGenerating) {
      return;
    }
    if (activeSession && activeSession.id === sessionId) {
      return;
    }

    try {
      setActiveSession(await api.getSession(sessionId));
    } catch (requestError) {
      triggerError(
        requestError instanceof Error
          ? requestError.message
          : "Could not open the session",
      );
    }
  }

  async function deleteSession(e: React.MouseEvent, sessionId: string) {
    e.stopPropagation();
    if (isGenerating) {
      return;
    }

    try {
      await api.deleteSession(sessionId);
      setActiveSession(null);
      setSessions(prevSessions => prevSessions.filter(session => session.id !== sessionId));
    } catch (requestError) {
      triggerError(
        requestError instanceof Error
          ? requestError.message
          : "Could not delete the session",
      );
    } finally {
      setMenuOpenId(null);
    }
  }

  async function clearChatHistory(e: React.MouseEvent, sessionId: string) {
    e.stopPropagation();
    if (isGenerating) {
      return;
    }

    try {
      setActiveSession(await api.clearChatHistory(sessionId));
    } catch (requestError) {
      triggerError(
        requestError instanceof Error
          ? requestError.message
          : "Could not clear the session",
      );
    } finally {
      setMenuOpenId(null);
    }
  }

  async function renameSession(sessionId: string) {
    if (isGenerating) {
      return;
    }

    try {
      await api.renameSession(sessionId, editTitleText);
      setSessions(prevSessions =>
        prevSessions.map((session) =>
          session.id === sessionId
            ? { ...session, title: editTitleText }
            : session
        )
      );
    } catch (requestError) {
      triggerError(
        requestError instanceof Error
          ? requestError.message
          : "Could not clear the session",
      );
    } finally {
      setEditingChatId(null);
    }
  }

  function handleStartEdit (e: React.MouseEvent, chat: SessionSummary) {
    e.stopPropagation();
    setEditingChatId(chat.id);
    setEditTitleText(chat.title);
    setMenuOpenId(null);
  }

  useEffect(() => {
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }

    void refreshSessions();
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: PointerEvent) => {
      if (chatActionsRef.current && !chatActionsRef.current.contains(event.target as Node)) {
        setMenuOpenId(null);
      }
    };

    if (menuOpenId) {
      document.addEventListener('pointerdown', handleClickOutside, true);
    }

    return () => {
      document.removeEventListener('pointerdown', handleClickOutside, true);
    };
  }, [menuOpenId]);

  useEffect(() => {
    if (!sidebarOpen || window.innerWidth >= 768) {
      return;
    }
    const handleClickOutside = (event: PointerEvent) => {
      if (sidebarRef.current && !sidebarRef.current.contains(event.target as Node)) {
        setSidebarOpen(false);
      }
    };

    document.addEventListener('pointerdown', handleClickOutside, true);

    return () => {
      document.removeEventListener('pointerdown', handleClickOutside, true);
    };
  }, [sidebarOpen]);

  return (
    <aside ref={sidebarRef} className={`fixed md:relative inset-y-0 left-0 z-50 flex flex-col border-r border-[#dadce0] dark:border-[#3c4043] bg-[#f8f9fa] dark:bg-[#1e1f20] transition-all duration-300 ease-in-out z-50 ${sidebarOpen ? 'w-72' : 'w-0 overflow-hidden md:w-0'}`}>
        <div className="flex items-center justify-between p-3 h-16 border-b border-[#dadce0]/50 dark:border-[#3c4043]/50">
          <div className={`flex items-center gap-3 overflow-hidden ${!sidebarOpen && 'md:hidden'}`}>
            <div className="flex items-center justify-center w-9 h-9 bg-white dark:bg-[#2d2e30] rounded-full shadow-sm border border-[#dadce0] dark:border-[#5f6368]">
              <Sparkles className="w-5 h-5 text-[#1a73e8] dark:text-[#8ab4f8]" />
            </div>
            <span className="font-extrabold text-base tracking-tight text-[#202124] dark:text-[#e3e3e3] whitespace-nowrap">AI Chatbot</span>
          </div>
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 rounded-full hover:bg-[#e8eaed] dark:hover:bg-[#303134] text-[#5f6368] dark:text-[#9aa0a6]">
            <Menu className="w-5 h-5" />
          </button>
        </div>

        <div className="p-3">
          {sidebarOpen && (
            <div onClick={() => {
              if (window.innerWidth < 768) setSidebarOpen(false);
              setActiveSession(null);
            }} className={`text-sm flex items-center gap-2 w-full rounded-full cursor-pointer font-medium py-1 px-3 transition-all ${!activeSession ? 'bg-[#d3e3fd] dark:bg-[#004a77] text-[#041e49] dark:text-[#c2e7ff] font-bold' : 'font-medium hover:bg-[#eef1f4] dark:hover:bg-[#2d2e30] text-[#3c4043] dark:text-[#c4c7c5]'}`}>
              <SquarePen size="16"/>
              <span>New Chat</span>
            </div>
            )}
        </div>

        {sidebarOpen && (
        <div className="flex-1 overflow-y-auto px-2 space-y-1 py-1">
          <span className="text-sm flex items-center gap-2 w-full text-[#001d35] dark:text-[#c2e7ff] font-bold py-1 px-3">Chats</span>
          {sessions.map(chat => {
            const isActive = chat.id === activeSession?.id;
            const isEditing = editingChatId === chat.id;
            const isMenuOpen = menuOpenId === chat.id;

            return (
              <div key={chat.id} onClick={() => { if (!isEditing) openSession(chat.id); if (window.innerWidth < 768) setSidebarOpen(false);}} className={`group relative flex items-center justify-between px-3 py-1 rounded-full cursor-pointer text-sm transition-colors ${isActive ? 'bg-[#d3e3fd] dark:bg-[#004a77] text-[#041e49] dark:text-[#c2e7ff] font-bold' : 'font-medium hover:bg-[#eef1f4] dark:hover:bg-[#2d2e30] text-[#3c4043] dark:text-[#c4c7c5]'}`}>
                <div className="flex items-center truncate flex-1 mr-2">
                  {isEditing ? (
                    <div className="flex items-center gap-1 w-full" onClick={e => e.stopPropagation()}>
                      <input type="text" value={editTitleText} onChange={e => setEditTitleText(e.target.value)} autoFocus className="bg-white dark:bg-[#131314] text-[#202124] dark:text-white px-2 py-0.5 rounded text-xs w-full border border-[#1a73e8] focus:outline-none" />
                      <button onClick={() => renameSession(chat.id)} className="p-1 text-green-600 rounded"><Check className="w-3.5 h-3.5" /></button>
                      <button onClick={() => setEditingChatId(null)} className="p-1 text-red-600 rounded"><X className="w-3.5 h-3.5" /></button>
                    </div>
                  ) : (
                    <span className="text-xs truncate">{chat.title}</span>
                  )}
                </div>

                {!isEditing && (
                  <div className="relative" ref={chatActionsRef}>
                    <button onClick={(e) => { e.stopPropagation(); setMenuOpenId(isMenuOpen ? null : chat.id); }} className="p-1 rounded-full opacity-0 group-hover:opacity-100 hover:bg-black/10 transition-opacity">
                      <MoreVertical className="w-4 h-4 text-[#5f6368]" />
                    </button>
                    {isMenuOpen && (
                      <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-[#28292a] border border-[#dadce0] dark:border-[#3c4043] rounded-lg shadow-lg py-1 z-50">
                        <button onClick={(e) => handleStartEdit(e, chat)} className="flex items-center gap-2.5 w-full px-4 py-2 text-xs text-[#3c4043] dark:text-[#e3e3e3] hover:bg-[#f1f3f4] dark:hover:bg-[#353638]"><Edit2 className="w-3.5 h-3.5" /> Rename</button>
                        <button onClick={(e) => clearChatHistory(e, chat.id)} className="flex items-center gap-2.5 w-full px-4 py-2 text-xs text-[#3c4043] dark:text-[#e3e3e3] hover:bg-[#f1f3f4] dark:hover:bg-[#353638]"><RotateCcw className="w-3.5 h-3.5" /> Clear History</button>
                        <button onClick={(e) => deleteSession(e, chat.id)} className="flex items-center gap-2.5 w-full px-4 py-2 text-xs text-red-600 hover:bg-red-50"><Trash2 className="w-3.5 h-3.5" /> Delete</button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>)}
    </aside>
  );
}

export default Sidebar;