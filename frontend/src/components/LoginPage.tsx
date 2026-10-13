import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useAppContext } from "../Context";

const GOOGLE_SCRIPT_URL = "https://accounts.google.com/gsi/client";

type GoogleCredentialResponse = { credential: string };

interface GoogleIdentityApi {
  initialize(options: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
  }): void;
  renderButton(
    parent: HTMLElement,
    options: { theme: string; size: string; text: string; shape: string; width: number },
  ): void;
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleIdentityApi } };
  }
}

// Loads Google Identity Services once, when the sign-in page first needs it
function loadGoogleScript(): Promise<void> {
  if (window.google) {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = GOOGLE_SCRIPT_URL;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Could not load Google sign-in"));
    document.head.appendChild(script);
  });
}

const LoginPage = () => {
  const { theme, signIn, notifyError } = useAppContext();
  const buttonRef = useRef<HTMLDivElement>(null);
  const [setupError, setSetupError] = useState<string | null>(null);
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;

  useEffect(() => {
    if (!clientId) {
      setSetupError("Google sign-in is not configured. Set VITE_GOOGLE_CLIENT_ID.");
      return;
    }

    let cancelled = false;

    loadGoogleScript()
      .then(() => {
        if (cancelled || !buttonRef.current || !window.google) {
          return;
        }

        // Google draws its own button, so it is redrawn when the theme changes
        buttonRef.current.innerHTML = "";
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: async ({ credential }) => {
            try {
              signIn(await api.signInWithGoogle(credential));
            } catch (requestError) {
              notifyError(requestError instanceof Error ? requestError.message : "Sign-in failed");
            }
          },
        });
        window.google.accounts.id.renderButton(buttonRef.current, {
          theme: theme === "dark" ? "filled_black" : "outline",
          size: "large",
          text: "signin_with",
          shape: "pill",
          width: 260,
        });
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setSetupError(error.message);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [clientId, theme]);

  return (
    <div className="flex h-dvh w-screen items-center justify-center bg-white dark:bg-[#131314] p-4 font-sans text-[#202124] dark:text-[#e3e3e3]">
      <div className="w-full max-w-sm rounded-2xl border border-[#dadce0] dark:border-[#3c4043] bg-white dark:bg-[#1e1f20] p-8 text-center shadow-sm">
        <h1 className="text-xl font-semibold">AI Chat</h1>
        <p className="mt-2 text-sm text-[#5f6368] dark:text-[#9aa0a6]">
          Sign in with Google to continue your chats.
        </p>
        <div ref={buttonRef} className="mt-6 flex justify-center" />
        {setupError && (
          <p className="mt-4 text-sm text-red-600 dark:text-red-400">{setupError}</p>
        )}
      </div>
    </div>
  );
};

export default LoginPage;
