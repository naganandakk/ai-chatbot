import {
  Bot, Sparkles, Code, Compass
} from 'lucide-react';
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../api";
import CopyContentBtn from './CopyContentBtn';
import CopyResponseBtn from './CopyResponseBtn';
import { useAppContext } from "../Context";
import SourcesBtn from "./SourcesBtn";
import PromptInput from './PromptInput';

const ChatContainer = () => {
  const {
    activeSession,
    isGenerating,
    setInputMessage
  } = useAppContext();
  const streamingIcon = (
    isGenerating && (
      <div className="flex items-start gap-4 justify-start">
        <div className="w-8 h-8 rounded-full bg-[#1a73e8] flex items-center justify-center text-white flex-shrink-0 animate-pulse-slow"><Bot className="w-4 h-4" /></div>
        <div className="border border-[#dadce0]/60 dark:border-[#3c4043] rounded-2xl rounded-tl-none px-4 py-3">
          <div className="flex items-center gap-1.5 py-1">
            <div className="w-2 h-2 rounded-full bg-[#1a73e8] animate-bounce"></div>
            <div className="w-2 h-2 rounded-full bg-[#1a73e8] animate-bounce" style={{ animationDelay: '150ms' }}></div>
          </div>
        </div>
      </div>
    )
  );
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
        <div key={idx}>
          <div className={`flex items-start gap-4 justify-end`}>
            <div className={`max-w-[100%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${msg.role === 'user' ? 'bg-[#f0f4f9] dark:bg-[#2b2d31] text-[#202124] dark:text-[#e3e3e3] rounded-tr-none' : 'rounded-tl-none'}`}>
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
            </div>
          </div>
          <div className="mt-4 flex items-center gap-2">
            {msg.role === 'assistant' && !(isGenerating && idx === (activeSession?.messages.length ?? 0) - 1) && (
              <CopyResponseBtn targetId={`response-${idx}`} />
            )}
            <SourcesBtn sources={msg.sources} id={idx} />
          </div>
        </div>
      ))
    }
    {streamingIcon}
  </>
  );
  const chatContainerContent = !activeSession || activeSession?.messages.length === 0 ? newChat : messageList

  return (
    <>
      <div className="flex-1 overflow-y-auto p-4 w-full">
        <div className="max-w-3xl mx-auto w-full space-y-6">
          {chatContainerContent}
        </div>
      </div>
      <div className="p-4 bg-white dark:bg-[#131314]">
        <div className="max-w-3xl mx-auto w-full">
          <PromptInput/>
        </div>
      </div>
    </>
  );
}

export default ChatContainer;