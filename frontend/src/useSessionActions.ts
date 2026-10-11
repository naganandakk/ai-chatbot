import { api } from "./api";
import { useAppContext } from "./Context";

// Rename, clear, and delete for a session, shared by the sidebar and the header menu.
// Failures are shown as notifications instead of being thrown, so callers can tidy up after `await`.
export const useSessionActions = () => {
  const {
    sessions, setSessions,
    setActiveSession,
    isGenerating,
    notifyError, notifySuccess,
  } = useAppContext();

  const deleteChat = async (sessionId: string) => {
    if (isGenerating) {
      return;
    }

    try {
      await api.deleteSession(sessionId);
      setActiveSession(null);
      setSessions(prevSessions => prevSessions.filter(session => session.id !== sessionId));
      notifySuccess("Chat deleted");
    } catch (requestError) {
      notifyError(
        requestError instanceof Error
          ? requestError.message
          : "Could not delete the session",
      );
    }
  };

  const clearChat = async (sessionId: string) => {
    if (isGenerating) {
      return;
    }

    try {
      setActiveSession(await api.clearChatHistory(sessionId));
      notifySuccess("Chat history cleared");
    } catch (requestError) {
      notifyError(
        requestError instanceof Error
          ? requestError.message
          : "Could not clear the session",
      );
    }
  };

  const renameChat = async (sessionId: string, title: string) => {
    const trimmedTitle = title.trim();
    const currentSession = sessions.find(session => session.id === sessionId);
    if (isGenerating || !trimmedTitle || currentSession?.title === trimmedTitle) {
      return;
    }

    try {
      await api.renameSession(sessionId, trimmedTitle);
      notifySuccess("Chat renamed");
      setSessions(prevSessions =>
        prevSessions.map((session) =>
          session.id === sessionId
            ? { ...session, title: trimmedTitle }
            : session
        )
      );
    } catch (requestError) {
      notifyError(
        requestError instanceof Error
          ? requestError.message
          : "Could not rename the session",
      );
    }
  };

  return { deleteChat, clearChat, renameChat };
};
