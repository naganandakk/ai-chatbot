import {
  ArrowDown, Sparkles, Code, Compass
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../api";
import CopyContentBtn from './CopyContentBtn';
import CopyMessageBtn from './CopyMessageBtn';
import CopyResponseBtn from './CopyResponseBtn';
import { useAppContext } from "../Context";
import SourcesBtn from "./SourcesBtn";
import MoreOptionsBtn from './MoreOptionsBtn';
import PromptInput from './PromptInput';

const ChatContainer = () => {
  const {
    activeSession,
    isLoadingSession,
    isGenerating,
    setInputMessage
  } = useAppContext();
  // Index of the user message whose copy button is revealed by a click
  const [copyableIdx, setCopyableIdx] = useState<number | null>(null);
  const hideCopyable = useCallback(() => setCopyableIdx(null), []);

  // Shows the scroll-to-bottom button only when the latest content is out of view
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const updateScrollToBottom = useCallback(() => {
    const element = scrollRef.current;
    if (!element) {
      return;
    }

    const distanceFromBottom = element.scrollHeight - element.scrollTop - element.clientHeight;
    setShowScrollToBottom(distanceFromBottom > 80);
  }, []);

  // Streamed text grows the list without firing a scroll event, so re-check on every update
  useEffect(() => {
    updateScrollToBottom();
  }, [activeSession, updateScrollToBottom]);

  const scrollToBottom = () => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  };

  // Scrolls the new response to the top of the view when a prompt is submitted
  useEffect(() => {
    const container = scrollRef.current;
    const responses = container?.querySelectorAll<HTMLElement>('[data-assistant-message]');
    const latestResponse = responses?.[responses.length - 1];
    if (!container || !isGenerating || !latestResponse) {
      return;
    }

    const top = latestResponse.getBoundingClientRect().top
      - container.getBoundingClientRect().top
      + container.scrollTop;
    container.scrollTo({ top, behavior: 'smooth' });
  }, [isGenerating]);

  // Hides the copy button when the user clicks anywhere outside its message
  useEffect(() => {
    if (copyableIdx === null) {
      return;
    }

    const hideOnOutsideClick = (event: MouseEvent) => {
      const target = event.target as Element;
      if (!target.closest(`[data-user-message="${copyableIdx}"]`)) {
        setCopyableIdx(null);
      }
    };

    document.addEventListener('mousedown', hideOnOutsideClick);
    return () => document.removeEventListener('mousedown', hideOnOutsideClick);
  }, [copyableIdx]);

  // Keeps text selection from toggling the copy button
  const toggleCopyable = (idx: number) => {
    if (window.getSelection()?.toString()) {
      return;
    }
    setCopyableIdx(copyableIdx === idx ? null : idx);
  };
  const newChat = (
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
  );
  const messageList = (
    <>
      {activeSession?.messages.map((msg: Message, idx: number) => (
        <div
          key={idx}
          data-assistant-message={msg.role === 'assistant' ? idx : undefined}
          // Gives the latest reply enough height to scroll its start to the top while it streams
          className={isGenerating && idx === (activeSession?.messages.length ?? 0) - 1 ? 'min-h-[100dvh]' : undefined}
        >
          <div className={`flex items-start gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`} data-user-message={msg.role === 'user' ? idx : undefined}>
            {msg.role === 'user' && copyableIdx === idx && (
              <CopyMessageBtn text={msg.content} onHide={hideCopyable} />
            )}
            <div
              onClick={msg.role === 'user' ? () => toggleCopyable(idx) : undefined}
              className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${msg.role === 'user' ? 'max-w-[100%] bg-[#f0f4f9] dark:bg-[#2b2d31] text-[#202124] dark:text-[#e3e3e3] rounded-tr-none cursor-pointer' : 'w-full rounded-tl-none'}`}>
              <div className="whitespace-pre-wrap" id={`response-${idx}`}>
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
              {/* Shown after the streamed text, so it moves with the reply as it grows */}
              {isGenerating && msg.role === 'assistant' && idx === (activeSession?.messages.length ?? 0) - 1 && (
                <div role="status" className="flex items-center gap-2 pt-2 text-xs text-[#5f6368] dark:text-[#9aa0a6]">
                  <Sparkles className="w-4 h-4 text-[#1a73e8] dark:text-[#8ab4f8] animate-pulse" />
                  <span>Generating</span>
                  <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#1a73e8] animate-bounce" />
                    <span className="w-1.5 h-1.5 rounded-full bg-[#1a73e8] animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-[#1a73e8] animate-bounce" style={{ animationDelay: '300ms' }} />
                  </span>
                </div>
              )}
            </div>
          </div>
          <div className="mt-2 flex items-center gap-2">
            {msg.role === 'assistant' && !(isGenerating && idx === (activeSession?.messages.length ?? 0) - 1) && (
              <CopyResponseBtn targetId={`response-${idx}`} />
            )}
            {msg.truncated && (
              <span className="text-xs text-[#b06000] dark:text-[#fdd663]">
                Reply stopped at the length limit
              </span>
            )}
            <SourcesBtn sources={msg.sources} id={idx} />
            {msg.role === 'assistant' && !(isGenerating && idx === (activeSession?.messages.length ?? 0) - 1) && (
              <MoreOptionsBtn
                model={msg.model}
                content={msg.content}
                playbackId={`${activeSession?.id}:${msg.createdAt}`}
              />
            )}
          </div>
        </div>
      ))
    }
  </>
  );
  const sessionLoader = (
    <div role="status" className="flex flex-col items-center justify-center h-[65vh] gap-3 text-sm text-[#5f6368] dark:text-[#9aa0a6]">
      <div className="w-8 h-8 rounded-full border-[3px] border-[#dadce0] dark:border-[#3c4043] border-t-[#1a73e8] dark:border-t-[#8ab4f8] animate-spin" />
      <span>Loading chat…</span>
    </div>
  );
  const chatContainerContent = isLoadingSession ? sessionLoader : !activeSession || activeSession?.messages.length === 0 ? newChat : messageList

  return (
    <>
      <div ref={scrollRef} onScroll={updateScrollToBottom} className="flex-1 overflow-y-auto p-4 w-full">
        <div className="max-w-3xl mx-auto w-full space-y-6">
          {chatContainerContent}
        </div>
      </div>
      <div className="p-4 bg-white dark:bg-[#131314]">
        <div className="max-w-3xl mx-auto w-full relative">
          {showScrollToBottom && (
            <button
              type="button"
              onClick={scrollToBottom}
              aria-label="Scroll to bottom"
              title="Scroll to bottom"
              className="absolute left-1/2 -translate-x-1/2 -top-14 z-10 p-2 rounded-full bg-white text-[#3c4043] shadow-md border border-[#dadce0] hover:bg-[#f1f3f4] transition-colors"
            >
              <ArrowDown className="w-5 h-5" />
            </button>
          )}
          <PromptInput/>
        </div>
      </div>
    </>
  );
}

export default ChatContainer;