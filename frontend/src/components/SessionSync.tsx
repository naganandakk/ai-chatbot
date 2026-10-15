import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, ChatSession, api } from "../api";
import { readCache } from "../cache";
import { useAppContext } from "../Context";

// Keeps the open chat in step with the /sessions/:sessionId URL, so refreshing a session URL reopens that session.
// Renders nothing; the chat state itself stays in the context.
const SessionSync = () => {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const {
    activeSession, setActiveSession, setIsLoadingSession, notifyError,
    sessions, currentUser,
  } = useAppContext();
  // The sidebar list says when each chat last changed. The effect re-runs when that changes, so a chat
  // updated elsewhere is fetched again
  const summary = sessions.find((session) => session.id === sessionId);
  const summaryUpdatedAt = summary?.updatedAt;

  useEffect(() => {
    if (!sessionId) {
      setActiveSession(null);
      return;
    }
    // The chat is already open at its latest version, e.g. right after a new chat was created and its URL was set
    if (activeSession?.id === sessionId && (!summary || activeSession.updatedAt === summary.updatedAt)) {
      return;
    }

    // A copy saved at the same updatedAt as the list is the current chat, so the server is not asked again
    const cached = currentUser && summary ? readCache<ChatSession>(currentUser.id, `session.${sessionId}`) : null;
    if (cached && summary && cached.data.updatedAt === summary.updatedAt) {
      setActiveSession({ ...cached.data, title: summary.title });
      return;
    }

    // A slow load for a session the user has already left must not overwrite the current one
    let cancelled = false;
    setIsLoadingSession(true);
    api.getSession(sessionId)
      .then((session) => {
        if (!cancelled) {
          setActiveSession(session);
        }
      })
      .catch((requestError) => {
        // A 401 means the sign-in ended, which the auth gate handles
        if (!cancelled && !(requestError instanceof ApiError && requestError.status === 401)) {
          notifyError(requestError instanceof Error ? requestError.message : "Could not open the session");
          navigate("/", { replace: true });
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingSession(false);
        }
      });

    return () => {
      cancelled = true;
      setIsLoadingSession(false);
    };
  }, [sessionId, summaryUpdatedAt]);

  return null;
};

export default SessionSync;
