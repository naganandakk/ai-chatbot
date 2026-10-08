import React, { useState, useRef, useEffect, useContext } from 'react';
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
import Sidebar from './components/Sidebar';
import { Context } from "./Context";

export default function App() {
  const {
    sidebarOpen, setSidebarOpen,
    activeSession, setActiveSession,
    sessions, setSessions,
    error, setError,
    isGenerating, setIsGenerating,
    menuOpenId, setMenuOpenId,
    editingChatId, setEditingChatId,
    editTitleText, setEditTitleText
  } = useContext(Context);
  const [inputMessage, setInputMessage] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
  };

  async function createSession() {
    if (isGenerating) {
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

  return (
    <div className="font-sans flex h-screen w-screen overflow-hidden bg-white dark:bg-[#131314] text-[#202124] dark:text-[#e3e3e3]">
      <Sidebar/>
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