import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from "react-markdown";
import {
  MessageSquare, Plus, Send, Menu, Moon, Sun, SquarePen,
  MoreVertical, Edit2, Trash2, RotateCcw, Bot, User,
  Sparkles, Code, Compass, HelpCircle, ArrowRight, Check, X, ChevronUp
} from 'lucide-react';
import remarkGfm from "remark-gfm";
import { api, ChatSession, Message, SessionSummary } from "./api";
import CopyContentBtn from './components/CopyContentBtn';
import SourcesBtn from './components/SourcesBtn';

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSession, setActiveSession] = useState<ChatSession | null>(null);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [error, setError] = useState("");
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editTitleText, setEditTitleText] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatActionsRef = useRef(null);
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [activeSession]);

  async function refreshSessions() {
    try {
      setSessions(await api.listSessions());
      if (sessions.length > 0) {
        setActiveSession(await api.getSession(sessions[0].id));
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load sessions",
      );
    }
  }

  useEffect(() => {
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
    scrollToBottom();
    void refreshSessions();
  }, []);

   useEffect(() => {
    const handleClickOutside = (event) => {
      if (chatActionsRef.current && !chatActionsRef.current.contains(event.target)) {
        setMenuOpenId(null);
      }
    };

    if (menuOpenId) {
      document.addEventListener('mousedown', handleClickOutside, true);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside, true);
    };
  }, [menuOpenId]);

  async function createSession() {
    if (isStreaming) {
      return;
    }

    try {
      setError("");
      const session = await api.createSession();
      setActiveSession(session);
      setSessions([...sessions, session])
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not create a session",
      );
    }
  }

  async function openSession(sessionId: string) {
    if (isGenerating) {
      return;
    }

    try {
      setError("");
      setActiveSession(await api.getSession(sessionId));
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not open the session",
      );
    }
  }

  async function handleSendMessage (e?: React.FormEvent) {
    e?.preventDefault();
    if (!inputMessage.trim() || isGenerating) return;

    const userText = inputMessage.trim();
    setInputMessage('');
    setIsGenerating(true);

    try {
      let session = activeSession;
      if (!session) {
        session = await api.createSession();
      }

      const userMessage: Message = {
        role: "user",
        content: userText,
        createdAt: new Date().toISOString(),
      };

      setActiveSession({
        ...session,
        messages: [...session.messages, userMessage],
      });

      await api.streamMessage(session.id, userText, (chunk) => {
        setActiveSession((currentSession) => {
          if (!currentSession || currentSession.id !== session.id) {
            return currentSession;
          }

          const messages = [...currentSession.messages];
          const lastMessage = messages[messages.length - 1];

          messages[messages.length - 1] = {
            ...lastMessage,
            content: lastMessage.content + chunk,
          };

          return { ...currentSession, messages };
        });
      });

      const updatedSession = await api.getSession(session.id);
      setActiveSession(updatedSession);
      const isExistingSession = sessions.some(s => s.id == updatedSession.id);
      if (!isExistingSession) {
        setSessions([
          {id: updatedSession.id, title: updatedSession.title}, ...sessions
        ])
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The assistant could not respond",
      );
    } finally {
      setIsGenerating(false);
    }
  }

  async function deleteSession(e: React.MouseEvent, sessionId: string) {
    e.stopPropagation();
    if (isGenerating) {
      return;
    }

    try {
      setError("");
      await api.deleteSession(sessionId);
      setActiveSession(null);
      setSessions(prevSessions => prevSessions.filter(session => session.id !== sessionId));
    } catch (requestError) {
      setError(
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
      setError("");
      setActiveSession(await api.clearChatHistory(sessionId));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not clear the session",
      );
    } finally {
      setMenuOpenId(null);
    }
  }

  const handleStartEdit = (e: React.MouseEvent, chat: ChatSession) => {
    e.stopPropagation();
    setEditingChatId(chat.id);
    setEditTitleText(chat.title);
    setMenuOpenId(null);
  };

  async function renameSession(sessionId: string) {
    if (!editTitleText.trim()) return;

    try {
      setError("");
      await api.renameSession(sessionId, editTitleText);
      setSessions(prevSessions =>
        prevSessions.map(session => {
          if (session.id === sessionId) {
            return { ...session, title: editTitleText };
          }
          return session;
        })
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not rename the session",
      );
    } finally {
      setEditingChatId(null);
    }
  }

  return (
    <div className="font-sans flex h-screen w-screen overflow-hidden bg-white dark:bg-[#131314] text-[#202124] dark:text-[#e3e3e3]">
      <aside className={`fixed md:relative inset-y-0 left-0 z-50 flex flex-col border-r border-[#dadce0] dark:border-[#3c4043] bg-[#f8f9fa] dark:bg-[#1e1f20] transition-all duration-300 ease-in-out z-50 ${sidebarOpen ? 'w-72' : 'w-0 overflow-hidden md:w-0'}`}>
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

      <main className="flex-1 flex flex-col h-full relative overflow-hidden w-full">
        <header className="h-16 flex items-center gap-3 px-4 shrink-0">
          {!sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-2 rounded-full hover:bg-[#e8eaed] dark:hover:bg-[#303134] text-[#5f6368] dark:text-[#9aa0a6] transition-all"
              aria-label="Open Sidebar"
            >
              <Menu className="w-5 h-5" />
            </button>
          )}
          <h2 className="md:hidden text-md font-bold text-[#202124] dark:text-[#e3e3e3] truncate">
            AI Chatbot
          </h2>
        </header>

       <div className="flex-1 overflow-y-auto p-4 w-full">
          <div className="max-w-3xl mx-auto w-full space-y-6">
            {!activeSession || activeSession?.messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-[65vh] text-center px-4">
                <div className="w-16 h-16 bg-gradient-to-tr from-blue-500 to-indigo-600 rounded-2xl flex items-center justify-center shadow-lg mb-6 text-white">
                  <Sparkles className="w-8 h-8" />
                </div>
                <h2 className="text-2xl md:text-3xl font-medium tracking-tight text-[#202124] dark:text-white mb-2">Hello, how can I help you today?</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg mt-6">
                  {[{ title: 'Explain React Server Components', icon: Code }, { title: 'Plan a 3-day trip to Tokyo', icon: Compass }].map((item, idx) => (
                    <button key={idx} onClick={() => setInputMessage(item.title)} className="flex items-center gap-3 p-3 rounded-xl border border-[#dadce0] dark:border-[#3c4043] hover:bg-[#f8f9fa] dark:hover:bg-[#1e1f20] text-left text-xs md:text-sm text-[#3c4043] dark:text-[#c4c7c5]">
                      <item.icon className="w-4 h-4 text-[#1a73e8]" />
                      <span className="flex-1 truncate">{item.title}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              activeSession?.messages.map((msg, idx) => (
              <div key={idx}>
                <div className={`flex items-start gap-4 justify-end`}>
                  <div className={`max-w-[100%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${msg.role === 'user' ? 'bg-[#f0f4f9] dark:bg-[#2b2d31] text-[#202124] dark:text-[#e3e3e3] rounded-tr-none' : 'rounded-tl-none'}`}>
                    <div className="whitespace-pre-wrap">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        // Paragraph Sizing (Standard text blocks)
                        p: ({ children }) => (
                          <p className="mt-0 mb-0 text-base leading-normal tracking-normal font-normal">
                            {children}
                          </p>
                        ),

                        // Headings Scale
                        h1: ({ children }) => (
                          <h1 className="text-xl leading-tight tracking-tight font-semibold text-zinc-950 dark:text-white mt-2.5 mb-1">
                            {children}
                          </h1>
                        ),
                        h2: ({ children }) => (
                          <h2 className="text-lg leading-snug tracking-tight font-semibold text-zinc-950 dark:text-white mt-2 mb-1">
                            {children}
                          </h2>
                        ),
                        h3: ({ children }) => (
                          <h3 className="text-md leading-snug tracking-normal font-semibold text-zinc-900 dark:text-zinc-200 mt-1.5 mb-0.5">
                            {children}
                          </h3>
                        ),

                        // Lists Layout Scale
                        ul: ({ children }) => (
                          <ul className="list-disc pl-5 mt-0 mb-0 space-y-0 text-base leading-normal">
                            {children}
                          </ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="list-decimal pl-5 mt-0 mb-0 space-y-0 text-base leading-normal">
                            {children}
                          </ol>
                        ),
                        li: ({ children }) => (
                          <li className="pl-0.5 [&>p]:inline [&>p]:mb-0 [&>p]:mt-0">{children}</li>
                        ),

                        // Tables Styling
                        table: ({ children }) => (
                          <div className="my-2 overflow-x-auto rounded-md border border-zinc-200 dark:border-zinc-800">
                            <table className="w-full text-left text-sm border-collapse m-0">
                              {children}
                            </table>
                          </div>
                        ),
                        thead: ({ children }) => (
                          <thead className="bg-zinc-100 dark:bg-zinc-800/60 border-b border-zinc-200 dark:border-zinc-800">
                            {children}
                          </thead>
                        ),
                        tbody: ({ children }) => (
                          <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                            {children}
                          </tbody>
                        ),
                        tr: ({ children }) => (
                          <tr className="hover:bg-zinc-50/50 dark:hover:bg-zinc-800/30">
                            {children}
                          </tr>
                        ),
                        th: ({ children }) => (
                          <th className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-900 dark:text-zinc-200 [&>p]:inline [&>p]:m-0">
                            {children}
                          </th>
                        ),
                        td: ({ children }) => (
                          <td className="px-3 py-1.5 text-zinc-800 dark:text-zinc-300 [&>p]:inline [&>p]:m-0">
                            {children}
                          </td>
                        ),

                        // Inline Code & Blocks Scale
                        // Gemini renders monospaced components exactly 1px down from normal variant text
                        code: ({ children, ...props }) => {
                          const isBlock = props.className?.includes('language-');
                          if (isBlock) return <code {...props}>{children}</code>;

                          return (
                            <code
                              className="bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-200 px-1 py-0.5 rounded text-sm font-mono border border-zinc-200/50 dark:border-zinc-700/50 break-words"
                              {...props}
                            >
                              {children}
                            </code>
                          );
                        },

                        pre: ({ children, ...props }) => (
                          <div className="relative group my-1.5 rounded-lg overflow-hidden bg-zinc-900 border border-zinc-800">
                            <CopyContentBtn>{children}</CopyContentBtn>
                            <pre className="p-2.5 overflow-x-auto text-sm leading-5 text-zinc-100 m-0" {...props}>
                              {children}
                            </pre>
                          </div>
                        ),

                        // Bold Text Configuration
                        strong: ({ children }) => (
                          <strong className="font-semibold text-zinc-950 dark:text-white">
                            {children}
                          </strong>
                        )
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                    </div>
                  </div>
                </div>
                <div className="mt-4">
                  {msg.role === 'assistant' && msg.sources?.length > 0 && (
                  <SourcesBtn sources={msg.sources} id={idx} />
                  )}
                </div>
              </div>
              ))
            )}

            {isGenerating && (
              <div className="flex items-start gap-4 justify-start">
                <div className="w-8 h-8 rounded-full bg-[#1a73e8] flex items-center justify-center text-white flex-shrink-0 animate-pulse-slow"><Bot className="w-4 h-4" /></div>
                <div className="border border-[#dadce0]/60 dark:border-[#3c4043] rounded-2xl rounded-tl-none px-4 py-3">
                  <div className="flex items-center gap-1.5 py-1">
                    <div className="w-2 h-2 rounded-full bg-[#1a73e8] animate-bounce"></div>
                    <div className="w-2 h-2 rounded-full bg-[#1a73e8] animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="p-4 bg-white dark:bg-[#131314]">
          <div className="max-w-3xl mx-auto w-full">
            <form onSubmit={handleSendMessage} className="relative flex items-center bg-[#f0f4f9] dark:bg-[#1e1f20] rounded-3xl border border-transparent focus-within:border-[#dadce0]">
              <input type="text" value={inputMessage} onChange={e => setInputMessage(e.target.value)} placeholder="Enter a prompt here..." className="w-full bg-transparent py-4 pl-6 pr-14 text-sm text-[#202124] dark:text-[#e3e3e3] focus:outline-none" />
              <button type="submit" disabled={!inputMessage.trim() || isGenerating} className={`absolute right-3 p-2 rounded-full ${inputMessage.trim() && !isGenerating ? 'bg-[#1a73e8] text-white' : 'text-[#9aa0a6] cursor-not-allowed'}`}>
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}