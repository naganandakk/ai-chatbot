import React, { useRef, useEffect, useState } from 'react';
import {
  Menu, SquarePen, MoreVertical, Edit2, Trash2, RotateCcw, Sparkles, Moon, Sun, Settings, LogOut, ChevronUp
} from 'lucide-react';
import { useNavigate } from "react-router-dom";
import { api, SessionSummary } from "../api";
import { useAppContext } from "../Context";
import ConfirmModal from "./ConfirmModal";
import RenameModal from "./RenameModal";
import { useSessionActions } from "../useSessionActions";

const Sidebar = () => {
  const {
    sidebarOpen, setSidebarOpen,
    activeSession,
    requestPromptFocus,
    sessions, setSessions,
    notifyError, notifySuccess,
    isGenerating, setIsGenerating,
    menuOpenId, setMenuOpenId,
    editingChatId, setEditingChatId,
    theme, toggleTheme,
    currentUser, signOut
  } = useAppContext();
  const { deleteChat, clearChat, renameChat } = useSessionActions();
  const editingChat = sessions.find(session => session.id === editingChatId);
  const chatActionsRef = useRef<HTMLDivElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const [pendingConfirm, setPendingConfirm] = useState<{ action: 'delete' | 'clear'; sessionId: string } | null>(null);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [pictureFailed, setPictureFailed] = useState(false);
  const accountMenuRef = useRef<HTMLDivElement>(null);
  const pendingConfirmSession = sessions.find(session => session.id === pendingConfirm?.sessionId);
  // Opening a chat is done by the URL, see SessionSync
  const navigate = useNavigate();

  async function refreshSessions () {
    try {
      const sessionList = await api.listSessions()
      setSessions(sessionList);
    } catch (requestError) {
      notifyError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load sessions",
      );
    }
  }

  function openSession(sessionId: string) {
    if (isGenerating) {
      return;
    }
    if (activeSession && activeSession.id === sessionId) {
      return;
    }

    navigate(`/sessions/${sessionId}`);
  }

  function openConfirm(e: React.MouseEvent, action: 'delete' | 'clear', sessionId: string) {
    e.stopPropagation();
    if (isGenerating) {
      return;
    }

    setMenuOpenId(null);
    setPendingConfirm({ action, sessionId });
  }

  // On phones the sidebar covers the chat, so it closes once an action finishes
  function closeSidebarOnMobile() {
    if (window.innerWidth < 768) setSidebarOpen(false);
  }

  async function deleteSession(sessionId: string) {
    await deleteChat(sessionId);
    setMenuOpenId(null);
    setPendingConfirm(null);
    closeSidebarOnMobile();
  }

  async function clearChatHistory(sessionId: string) {
    await clearChat(sessionId);
    setMenuOpenId(null);
    setPendingConfirm(null);
    closeSidebarOnMobile();
  }

  function handleStartEdit (e: React.MouseEvent, chat: SessionSummary) {
    e.stopPropagation();
    setEditingChatId(chat.id);
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
      if (!chatActionsRef.current?.contains(event.target as Node)) {
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
    if (!accountMenuOpen) {
      return;
    }
    const handleClickOutside = (event: PointerEvent) => {
      if (!accountMenuRef.current?.contains(event.target as Node)) {
        setAccountMenuOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setAccountMenuOpen(false);
      }
    };

    document.addEventListener('pointerdown', handleClickOutside, true);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('pointerdown', handleClickOutside, true);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [accountMenuOpen]);

  useEffect(() => {
    // The footer unmounts with the sidebar, so its menu should not reappear on reopen
    if (!sidebarOpen) {
      setAccountMenuOpen(false);
    }
  }, [sidebarOpen]);

  useEffect(() => {
    // The dialogs sit outside the sidebar, so tapping them must not close the sidebar
    if (!sidebarOpen || window.innerWidth >= 768 || pendingConfirm || editingChatId) {
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
  }, [sidebarOpen, pendingConfirm, editingChatId]);

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
              navigate('/');
              requestPromptFocus();
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
            // Other chats can't be opened while a reply streams into the active one
            const isLocked = isGenerating && !isActive;

            return (
              <div key={chat.id} onClick={() => { if (!isEditing) openSession(chat.id); if (window.innerWidth < 768) setSidebarOpen(false);}} className={`group relative flex items-center justify-between px-3 py-1 rounded-full text-sm transition-colors ${isLocked ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} ${isActive ? 'bg-[#d3e3fd] dark:bg-[#004a77] text-[#041e49] dark:text-[#c2e7ff] font-bold' : `font-medium text-[#3c4043] dark:text-[#c4c7c5] ${isLocked ? '' : 'hover:bg-[#eef1f4] dark:hover:bg-[#2d2e30]'}`}`}>
                <div className="flex items-center truncate flex-1 mr-2">
                  <span className="text-xs truncate">{chat.title}</span>
                </div>

                {!isEditing && (
                  <div className="relative" ref={isMenuOpen ? chatActionsRef : undefined}>
                    <button onClick={(e) => { e.stopPropagation(); setMenuOpenId(isMenuOpen ? null : chat.id); }} className="p-1 rounded-full opacity-100 md:opacity-0 md:group-hover:opacity-100 hover:bg-black/10 transition-opacity">
                      <MoreVertical className="w-4 h-4 text-[#5f6368] dark:text-[#c4c7c5]" />
                    </button>
                    {isMenuOpen && (
                      <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-[#28292a] border border-[#dadce0] dark:border-[#3c4043] rounded-lg shadow-lg py-1 z-50">
                        <button onClick={(e) => handleStartEdit(e, chat)} className="flex items-center gap-2.5 w-full px-4 py-2 text-xs text-[#3c4043] dark:text-[#e3e3e3] hover:bg-[#f1f3f4] dark:hover:bg-[#353638]"><Edit2 className="w-3.5 h-3.5" /> Rename</button>
                        <button onClick={(e) => openConfirm(e, 'clear', chat.id)} className="flex items-center gap-2.5 w-full px-4 py-2 text-xs text-[#3c4043] dark:text-[#e3e3e3] hover:bg-[#f1f3f4] dark:hover:bg-[#353638]"><RotateCcw className="w-3.5 h-3.5" /> Clear History</button>
                        <button onClick={(e) => openConfirm(e, 'delete', chat.id)} className="flex items-center gap-2.5 w-full px-4 py-2 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40"><Trash2 className="w-3.5 h-3.5" /> Delete</button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>)}

        {/* Stays mounted while the sidebar is closed, so the avatar image is not reloaded on reopen */}
        {currentUser && (
          <div ref={accountMenuRef} className={`relative p-3 border-t border-[#dadce0]/50 dark:border-[#3c4043]/50 ${sidebarOpen ? '' : 'invisible'}`}>
            {accountMenuOpen && (
              <div role="menu" className="absolute bottom-full left-3 right-3 mb-2 bg-white dark:bg-[#28292a] border border-[#dadce0] dark:border-[#3c4043] rounded-lg shadow-lg py-1 z-50">
                <button
                  role="menuitemcheckbox"
                  aria-checked={theme === 'dark'}
                  onClick={() => {
                    toggleTheme();
                    setAccountMenuOpen(false);
                    closeSidebarOnMobile();
                  }}
                  className="flex items-center justify-between gap-2.5 w-full px-4 py-2 text-sm text-[#3c4043] dark:text-[#e3e3e3] hover:bg-[#f1f3f4] dark:hover:bg-[#353638]"
                >
                  <span className="flex items-center gap-2.5">
                    {theme === 'dark' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
                    <span>Dark mode</span>
                  </span>
                  <span className={`inline-flex items-center h-5 w-9 p-0.5 rounded-full transition-colors ${theme === 'dark' ? 'bg-[#8ab4f8]' : 'bg-[#dadce0]'}`}>
                    <span className={`block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${theme === 'dark' ? 'translate-x-4' : 'translate-x-0'}`} />
                  </span>
                </button>
                <button
                  role="menuitem"
                  onClick={() => {
                    setAccountMenuOpen(false);
                    navigate("/settings");
                    closeSidebarOnMobile();
                  }}
                  className="flex items-center gap-2.5 w-full px-4 py-2 text-sm text-[#3c4043] dark:text-[#e3e3e3] hover:bg-[#f1f3f4] dark:hover:bg-[#353638]"
                >
                  <Settings className="w-4 h-4" />
                  <span>Settings</span>
                </button>
                <div className="my-1 border-t border-[#dadce0] dark:border-[#3c4043]" />
                <button
                  role="menuitem"
                  onClick={() => {
                    setAccountMenuOpen(false);
                    void signOut();
                    closeSidebarOnMobile();
                  }}
                  className="flex items-center gap-2.5 w-full px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Log out</span>
                </button>
              </div>
            )}
            <button
              onClick={() => setAccountMenuOpen(!accountMenuOpen)}
              aria-haspopup="menu"
              aria-expanded={accountMenuOpen}
              className="flex items-center gap-3 w-full rounded-full py-1.5 px-2 text-left hover:bg-[#eef1f4] dark:hover:bg-[#2d2e30] transition-colors"
            >
              {currentUser.picture && !pictureFailed ? (
                <img
                  src={currentUser.picture}
                  alt=""
                  referrerPolicy="no-referrer"
                  onError={() => setPictureFailed(true)}
                  className="w-8 h-8 shrink-0 rounded-full object-cover"
                />
              ) : (
                <span className="flex items-center justify-center w-8 h-8 shrink-0 rounded-full bg-[#e8f0fe] dark:bg-[#004a77] text-sm font-bold text-[#1a73e8] dark:text-[#c2e7ff]">
                  {(currentUser.name || currentUser.email).charAt(0).toUpperCase()}
                </span>
              )}
              <span className="flex-1 min-w-0">
                <span className="block truncate text-sm font-medium text-[#202124] dark:text-[#e3e3e3]">
                  {currentUser.name || currentUser.email}
                </span>
                {currentUser.name && (
                  <span className="block truncate text-xs text-[#5f6368] dark:text-[#9aa0a6]">
                    {currentUser.email}
                  </span>
                )}
              </span>
              <ChevronUp className="w-4 h-4 shrink-0 text-[#5f6368] dark:text-[#9aa0a6]" />
            </button>
          </div>
        )}

        {editingChat && (
          <RenameModal
            initialTitle={editingChat.title}
            onCancel={() => {
              setEditingChatId(null);
              closeSidebarOnMobile();
            }}
            onSave={async (title) => {
              setEditingChatId(null);
              await renameChat(editingChat.id, title);
              closeSidebarOnMobile();
            }}
          />
        )}

        {pendingConfirm && pendingConfirmSession && (
          pendingConfirm.action === 'delete' ? (
            <ConfirmModal
              heading="Delete chat?"
              message={<>
                <span className="font-medium text-[#3c4043] dark:text-[#c4c7c5]">&ldquo;{pendingConfirmSession.title}&rdquo;</span> will be permanently deleted. This can&apos;t be undone.
              </>}
              confirmLabel="Delete"
              onCancel={() => {
                setPendingConfirm(null);
                closeSidebarOnMobile();
              }}
              onConfirm={() => void deleteSession(pendingConfirm.sessionId)}
            />
          ) : (
            <ConfirmModal
              heading="Clear chat history?"
              message={<>
                All messages in <span className="font-medium text-[#3c4043] dark:text-[#c4c7c5]">&ldquo;{pendingConfirmSession.title}&rdquo;</span> will be removed. The chat itself will be kept. This can&apos;t be undone.
              </>}
              confirmLabel="Clear"
              onCancel={() => {
                setPendingConfirm(null);
                closeSidebarOnMobile();
              }}
              onConfirm={() => void clearChatHistory(pendingConfirm.sessionId)}
            />
          )
        )}
    </aside>
  );
}

export default Sidebar;