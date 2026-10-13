import { useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, api } from "../api";
import { useAppContext } from "../Context";

// Keeps the open chat in step with the /sessions/:sessionId URL, so refreshing a session URL reopens that session.
// Renders nothing; the chat state itself stays in the context.
const SessionSync = () => {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const { activeSession, setActiveSession, setIsLoadingSession, notifyError } = useAppContext();
  // Read by the effect below, so a change to the open chat does not re-run the load
  const activeSessionIdRef = useRef<string | null>(null);
  activeSessionIdRef.current = activeSession?.id ?? null;

  useEffect(() => {
    if (!sessionId) {
      setActiveSession(null);
      return;
    }
    // The chat is already open, e.g. right after a new chat was created and its URL was set
    if (activeSessionIdRef.current === sessionId) {
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
  }, [sessionId]);

  return null;
};

export default SessionSync;
