import {
  Send
} from 'lucide-react';
import { api, ChatSession, Message } from "../api";
import { useAppContext } from "../Context";

const PromptInput = () => {
  const {
    activeSession, setActiveSession,
    sessions, setSessions,
    isGenerating, setIsGenerating,
    inputMessage, setInputMessage,
    triggerError
  } = useAppContext();

  async function createSession() {
    if (isGenerating) {
      return;
    }

    try {
      const session = await api.createSession();
      setActiveSession(session);
      setSessions([...sessions, session])
    } catch (requestError) {
      triggerError(
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
      const session: ChatSession = activeSession ?? (await api.createSession());

      const userMessage: Message = {
        role: "user",
        content: userText,
        createdAt: new Date().toISOString(),
        sources: [],
        model: "",
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
          {
            id: updatedSession.id,
            title: updatedSession.title,
            createdAt: updatedSession.createdAt,
            updatedAt: updatedSession.updatedAt,
          }, ...sessions
        ])
      }
    } catch (requestError) {
      triggerError(
        requestError instanceof Error
          ? requestError.message
          : "The assistant could not respond",
      );
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <form onSubmit={handleSendMessage} className="relative flex items-center bg-[#f0f4f9] dark:bg-[#1e1f20] rounded-3xl border border-transparent focus-within:border-[#dadce0]">
      <input type="text" value={inputMessage} onChange={e => setInputMessage(e.target.value)} placeholder="Enter a prompt here..." className="w-full bg-transparent py-4 pl-6 pr-14 text-sm text-[#202124] dark:text-[#e3e3e3] focus:outline-none" />
      <button type="submit" disabled={!inputMessage.trim() || isGenerating} className={`absolute right-3 p-2 rounded-full ${inputMessage.trim() && !isGenerating ? 'bg-[#1a73e8] text-white' : 'text-[#9aa0a6] cursor-not-allowed'}`}>
        <Send className="w-4 h-4" />
      </button>
    </form>
)};

export default PromptInput;