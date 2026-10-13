import React from "react";
import { useAppContext } from "../Context";
import LoginPage from "./LoginPage";

// Shows the chat only to a signed-in user. Every URL shows the sign-in page until then,
// and the URL is kept, so signing in lands on the same chat.
const AuthGate = ({ children }: { children: React.ReactNode }) => {
  const { authStatus } = useAppContext();

  if (authStatus === "loading") {
    return <div className="h-dvh w-screen bg-white dark:bg-[#131314]" />;
  }

  if (authStatus === "anonymous") {
    return <LoginPage />;
  }

  return <>{children}</>;
};

export default AuthGate;
