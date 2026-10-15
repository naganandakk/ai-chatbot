import { useNavigate } from "react-router-dom";
import { api } from "./api";
import { removeCache } from "./cache";
import { useAppContext } from "./Context";

// Rename, clear, and delete for a session, shared by the sidebar and the header menu.
// Failures are shown as notifications instead of being thrown, so callers can tidy up after `await`.
export const useSessionActions = () => {
  const {
    sessions, setSessions,
    activeSession, setActiveSession,
    isGenerating,
    notifyError, notifySuccess,
    currentUser,
  } = useAppContext();
  const navigate = useNavigate();

  const deleteChat = async (sessionId: string) => {
    if (isGenerating) {
      return;
    }

    try {
      await api.deleteSession(sessionId);
      if (currentUser) {
        removeCache(currentUser.id, `session.${sessionId}`);
      }
      // Only leave the chat when it is the one open; deleting another chat keeps this one
      if (activeSession?.id === sessionId) {
        navigate("/");
      }
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
      const cleared = await api.clearChatHistory(sessionId);
      setActiveSession(cleared);
      // The cleared chat has a new title and updatedAt, which the sidebar entry must match
      setSessions(prevSessions =>
        prevSessions.map(session =>
          session.id === sessionId
            ? { ...session, title: cleared.title, updatedAt: cleared.updatedAt }
            : session
        )
      );
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
      // Renaming moves updatedAt on the server, so the sidebar entry takes the response's copy
      const renamed = await api.renameSession(sessionId, trimmedTitle);
      notifySuccess("Chat renamed");
      setSessions(prevSessions =>
        prevSessions.map((session) =>
          session.id === sessionId
            ? { ...session, title: trimmedTitle, updatedAt: renamed.updatedAt }
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
