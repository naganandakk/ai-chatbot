import {
  FileText, Paperclip, Send, X
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { checkAttachments, formatFileSize } from "../attachments";
import { api, AttachmentLimits, ChatSession, Message, SessionSummary, StreamError } from "../api";
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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [limits, setLimits] = useState<AttachmentLimits | null>(null);
  const isDesktop = useIsDesktop();
  const voice = useVoiceInput({
    currentText: inputMessage,
    onChange: setInputMessage,
    onError: notifyError,
  });

  useEffect(() => {
    api.getAttachmentLimits()
      .then(setLimits)
      .catch(() => {
        // Without the limits the picker accepts any file, and the server checks each upload
      });
  }, []);

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

  function addFiles(incoming: FileList | File[]) {
    // Copied now, since the file input is cleared right after this call
    const added = Array.from(incoming);
    if (added.length === 0) return;

    const problem = limits ? checkAttachments(added, files, limits) : null;
    if (problem) {
      notifyError(problem);
      return;
    }
    setFiles((current) => [...current, ...added]);
  }

  function removeFile(index: number) {
    setFiles((current) => current.filter((_, position) => position !== index));
  }

  async function handleSendMessage (e?: React.FormEvent) {
    e?.preventDefault();
    // Sending while a session loads could attach the message to the wrong chat
    const hasContent = inputMessage.trim() !== "" || files.length > 0;
    if (!hasContent || isGenerating || isLoadingSession) return;

    // Dictation must not write into the prompt after it has been sent and cleared
    voice.cancel();
    const userText = inputMessage.trim();
    const sentFiles = files;
    setInputMessage('');
    setFiles([]);
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
        // No ids yet. The saved message replaces this once the stream finishes.
        attachments: sentFiles.map((file) => ({
          id: "",
          filename: file.name,
          mediaType: file.type,
          size: file.size,
        })),
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
        sentFiles,
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
      if (requestError instanceof StreamError && requestError.code === "api_key_required") {
        // Nothing was saved for this message, so the user only needs to add a key
        navigate("/settings");
      }
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

  const canSend = (inputMessage.trim() !== "" || files.length > 0) && !isGenerating && !isLoadingSession;

  return (
    <form
      onSubmit={handleSendMessage}
      // Dropping files onto the prompt attaches them, as the paperclip does
      onDragOver={(e) => {
        if (e.dataTransfer.types.includes("Files") && !isGenerating) e.preventDefault();
      }}
      onDrop={(e) => {
        if (isGenerating) return;
        e.preventDefault();
        addFiles(e.dataTransfer.files);
      }}
      className={`flex flex-col bg-[#f0f4f9] dark:bg-[#1e1f20] rounded-3xl border focus-within:border-[#dadce0] transition-colors ${voice.isListening ? 'border-[#d93025] ring-2 ring-[#d93025]/20' : 'border-transparent'}`}>
      {files.length > 0 && (
        <ul aria-label="Attached files" className="flex flex-wrap gap-2 px-4 pt-3">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`} className="flex items-center gap-2 max-w-full rounded-xl border border-[#dadce0] dark:border-[#3c4043] bg-white dark:bg-[#303134] py-1 pl-2 pr-1 text-xs text-[#202124] dark:text-[#e3e3e3]">
              <FileText className="w-4 h-4 shrink-0 text-[#5f6368] dark:text-[#9aa0a6]" />
              <span className="truncate max-w-[12rem]">{file.name}</span>
              <span className="shrink-0 text-[#5f6368] dark:text-[#9aa0a6]">{formatFileSize(file.size)}</span>
              <button type="button" onClick={() => removeFile(index)} disabled={isGenerating} aria-label={`Remove ${file.name}`} title="Remove" className="shrink-0 p-1 rounded-full text-[#5f6368] dark:text-[#9aa0a6] hover:bg-[#e8eaed] dark:hover:bg-[#3c4043] transition-colors disabled:opacity-60 disabled:cursor-not-allowed">
                <X className="w-3 h-3" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex items-center gap-1">
        <input ref={inputRef} type="text" value={inputMessage} onChange={e => setInputMessage(e.target.value)} onPaste={(e) => {
          // Pasting an image or file from the clipboard attaches it
          if (e.clipboardData.files.length > 0) {
            e.preventDefault();
            addFiles(e.clipboardData.files);
          }
        }} placeholder={isLoadingSession ? "Loading chat..." : voice.isListening ? "Listening... speak your prompt" : "Enter a prompt here..."} className="min-w-0 w-full flex-1 bg-transparent py-4 pl-6 pr-2 text-base md:text-sm text-[#202124] dark:text-[#e3e3e3] focus:outline-none" />
        {isDesktop && <ModelPicker />}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isGenerating || isLoadingSession}
          aria-label="Attach files"
          title="Attach files"
          className="shrink-0 p-2 rounded-full text-[#5f6368] dark:text-[#9aa0a6] hover:bg-[#e8eaed] dark:hover:bg-[#303134] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
        >
          <Paperclip className="w-4 h-4" />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={limits?.acceptedExtensions.join(",")}
          className="hidden"
          onChange={(e) => {
            addFiles(e.target.files ?? []);
            e.target.value = "";
          }}
        />
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
        <button type="submit" disabled={!canSend} className={`shrink-0 mr-2 p-2 rounded-full ${canSend ? 'bg-[#1a73e8] text-white' : 'text-[#9aa0a6] cursor-not-allowed'}`}>
          <Send className="w-4 h-4" />
        </button>
      </div>
    </form>
)};

export default PromptInput;