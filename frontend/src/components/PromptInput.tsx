import {
  Send
} from 'lucide-react';
import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ChatSession, Message, SessionSummary, StreamError } from "../api";
import { useAppContext } from "../Context";
import { useIsDesktop } from "../useIsDesktop";
import { useVoiceInput } from "../voiceInput";
import ModelPicker from "./ModelPicker";
import VoiceInputBtn from "./VoiceInputBtn";

const PromptInput = () => {
  const {
    activeSession, setActiveSession,
    sessions, setSessions,
    isLoadingSession,
    isGenerating, setIsGenerating,
    inputMessage, setInputMessage,
    selectedModel,
    promptFocusRequest,
    notifyError
  } = useAppContext();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const isDesktop = useIsDesktop();
  const voice = useVoiceInput({
    currentText: inputMessage,
    onChange: setInputMessage,
    onError: notifyError,
  });

  // Focus the prompt when no chat is open. Desktop only, so phones don't pop the keyboard on load
  useEffect(() => {
    if (!activeSession && window.matchMedia('(min-width: 768px)').matches) {
      inputRef.current?.focus();
    }
  }, [activeSession]);

  // New Chat is a deliberate tap, so focus the prompt on every device
  useEffect(() => {
    if (promptFocusRequest > 0) {
      inputRef.current?.focus();
    }
  }, [promptFocusRequest]);

  // Keeps the sidebar entry in step with the server's title and updatedAt
  function upsertSessionSummary(summary: SessionSummary) {
    setSessions((current) =>
      current.some((existing) => existing.id === summary.id)
        ? current.map((existing) => (existing.id === summary.id ? summary : existing))
        : [summary, ...current],
    );
  }

  async function createSession() {
    if (isGenerating) {
      return;
    }

    try {
      const session = await api.createSession();
      setActiveSession(session);
      setSessions([...sessions, session])
    } catch (requestError) {
      notifyError(
        requestError instanceof Error
          ? requestError.message
          : "Could not create a session",
      );
    }
  }

  async function handleSendMessage (e?: React.FormEvent) {
    e?.preventDefault();
    // Sending while a session loads could attach the message to the wrong chat
    if (!inputMessage.trim() || isGenerating || isLoadingSession) return;

    // Dictation must not write into the prompt after it has been sent and cleared
    voice.cancel();
    const userText = inputMessage.trim();
    setInputMessage('');
    setIsGenerating(true);

    try {
      const isNewSession = !activeSession;
      const session: ChatSession = activeSession ?? (await api.createSession());

      const userMessage: Message = {
        role: "user",
        content: userText,
        createdAt: new Date().toISOString(),
        sources: [],
        model: "",
      };

      // Empty assistant message that the streamed chunks fill in
      const assistantMessage: Message = {
        role: "assistant",
        content: "",
        createdAt: new Date().toISOString(),
        sources: [],
        model: "",
      };

      setActiveSession({
        ...session,
        messages: [...session.messages, userMessage, assistantMessage],
      });
      // The URL follows the chat once it exists, so a refresh reopens it
      if (isNewSession) {
        navigate(`/sessions/${session.id}`);
      }

      await api.streamMessage(
        session.id,
        userText,
        selectedModel,
        (chunk) => {
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
        },
        () => {
          // Text streamed before a web search was narration, so the reply starts over
          setActiveSession((currentSession) => {
            if (!currentSession || currentSession.id !== session.id) {
              return currentSession;
            }

            const messages = [...currentSession.messages];
            messages[messages.length - 1] = {
              ...messages[messages.length - 1],
              content: "",
              sources: [],
            };

            return { ...currentSession, messages };
          });
        },
        ({ message, session: summary }) => {
          // The saved reply carries sources and the truncated flag, so it replaces the streamed placeholder
          setActiveSession((currentSession) => {
            if (!currentSession || currentSession.id !== session.id) {
              return currentSession;
            }

            const messages = [...currentSession.messages];
            messages[messages.length - 1] = message;

            return { ...currentSession, ...summary, messages };
          });
          upsertSessionSummary(summary);
        },
      );
    } catch (requestError) {
      if (requestError instanceof StreamError && requestError.session) {
        // The server kept the user's message without a reply, so show its copy of the session
        const serverSession = requestError.session;
        setActiveSession(serverSession);
        upsertSessionSummary({
          id: serverSession.id,
          title: serverSession.title,
          createdAt: serverSession.createdAt,
          updatedAt: serverSession.updatedAt,
        });
      } else {
        // Drop the empty assistant placeholder so no copy or sources buttons are left behind
        setActiveSession((currentSession) => {
          const lastMessage = currentSession?.messages[currentSession.messages.length - 1];
          if (!currentSession || lastMessage?.role !== "assistant" || lastMessage.content) {
            return currentSession;
          }
          return { ...currentSession, messages: currentSession.messages.slice(0, -1) };
        });
      }
      notifyError(
        requestError instanceof Error
          ? requestError.message
          : "The assistant could not respond",
      );
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <form onSubmit={handleSendMessage} className={`flex items-center gap-1 bg-[#f0f4f9] dark:bg-[#1e1f20] rounded-3xl border focus-within:border-[#dadce0] transition-colors ${voice.isListening ? 'border-[#d93025] ring-2 ring-[#d93025]/20' : 'border-transparent'}`}>
      <input ref={inputRef} type="text" value={inputMessage} onChange={e => setInputMessage(e.target.value)} placeholder={isLoadingSession ? "Loading chat..." : voice.isListening ? "Listening... speak your prompt" : "Enter a prompt here..."} className="min-w-0 w-full flex-1 bg-transparent py-4 pl-6 pr-2 text-base md:text-sm text-[#202124] dark:text-[#e3e3e3] focus:outline-none" />
      {isDesktop && <ModelPicker />}
      <VoiceInputBtn
        isListening={voice.isListening}
        disabled={isGenerating || isLoadingSession}
        onToggle={() => {
          if (voice.isListening) {
            voice.stop();
          } else if (voice.unsupportedReason) {
            notifyError(voice.unsupportedReason);
          } else {
            voice.start();
            inputRef.current?.focus();
          }
        }}
      />
      <button type="submit" disabled={!inputMessage.trim() || isGenerating || isLoadingSession} className={`shrink-0 mr-2 p-2 rounded-full ${inputMessage.trim() && !isGenerating && !isLoadingSession ? 'bg-[#1a73e8] text-white' : 'text-[#9aa0a6] cursor-not-allowed'}`}>
        <Send className="w-4 h-4" />
      </button>
    </form>
)};

export default PromptInput;