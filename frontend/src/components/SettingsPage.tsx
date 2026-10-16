import { useEffect, useState } from "react";
import { ArrowLeft, Check } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, ApiKeyStatus, UserSettings } from "../api";
import { readCache, removeCache, writeCache } from "../cache";
import { useAppContext } from "../Context";
import ConfirmModal from "./ConfirmModal";
import NotificationStack from "./NotificationStack";

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  openrouter: "OpenRouter",
};

const labelFor = (provider: string) => PROVIDER_LABELS[provider] ?? provider;

// Settings are a full page, so the chat keeps its place: going back returns to the same URL
const SettingsPage = () => {
  const navigate = useNavigate();
  const { notifySuccess, notifyError, currentUser } = useAppContext();
  const userId = currentUser?.id ?? null;
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busyProvider, setBusyProvider] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  function showSettings(next: UserSettings) {
    setSettings(next);
    if (userId) {
      writeCache(userId, "settings", next);
    }
  }

  // The model list depends on the provider and its key, so it is fetched again after either changes
  function forgetModelList() {
    if (userId) {
      removeCache(userId, "models");
    }
  }

  async function loadSettings() {
    try {
      showSettings(await api.getSettings());
    } catch (requestError) {
      notifyError(requestError instanceof Error ? requestError.message : "Could not load settings");
    }
  }

  useEffect(() => {
    // The saved copy is shown at once and replaced by the server's copy when it arrives
    const cached = userId ? readCache<UserSettings>(userId, "settings") : null;
    if (cached) {
      setSettings(cached.data);
    }
    loadSettings();
  }, []);

  function goBack() {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate("/");
    }
  }

  async function chooseProvider(provider: string) {
    if (settings?.activeProvider === provider) {
      return;
    }

    setBusyProvider(provider);
    try {
      showSettings(await api.updateSettings(provider));
      forgetModelList();
      notifySuccess(`${labelFor(provider)} is now in use`);
    } catch (requestError) {
      notifyError(requestError instanceof Error ? requestError.message : "Could not change the provider");
    } finally {
      setBusyProvider(null);
    }
  }

  async function saveKey(provider: string) {
    const apiKey = (drafts[provider] ?? "").trim();
    if (!apiKey) {
      return;
    }

    setBusyProvider(provider);
    setErrors((current) => ({ ...current, [provider]: "" }));
    try {
      await api.saveApiKey(provider, apiKey);
      forgetModelList();
      setDrafts((current) => ({ ...current, [provider]: "" }));
      notifySuccess(`${labelFor(provider)} key saved`);
      await loadSettings();
    } catch (requestError) {
      setErrors((current) => ({
        ...current,
        [provider]: requestError instanceof Error ? requestError.message : "Could not save the key",
      }));
    } finally {
      setBusyProvider(null);
    }
  }

  async function deleteKey(provider: string) {
    setPendingDelete(null);
    setBusyProvider(provider);
    try {
      await api.deleteApiKey(provider);
      forgetModelList();
      notifySuccess(`${labelFor(provider)} key deleted`);
      await loadSettings();
    } catch (requestError) {
      notifyError(requestError instanceof Error ? requestError.message : "Could not delete the key");
    } finally {
      setBusyProvider(null);
    }
  }

  const providers: ApiKeyStatus[] = settings?.providers ?? [];

  return (
    <div className="font-sans min-h-dvh w-screen bg-white dark:bg-[#131314] text-[#202124] dark:text-[#e3e3e3]">
      <NotificationStack />

      <header className="flex items-center gap-3 px-4 sm:px-8 py-4 border-b border-[#dadce0] dark:border-[#3c4043]">
        <button
          onClick={goBack}
          aria-label="Back"
          className="p-2 rounded-full hover:bg-[#f1f3f4] dark:hover:bg-[#353638]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-lg font-semibold">Settings</h1>
      </header>

      <main className="mx-auto w-full max-w-2xl space-y-8 px-4 sm:px-8 py-8">
        <section>
          <h2 className="text-base font-semibold">Provider in use</h2>
          <p className="mt-1 text-sm text-[#5f6368] dark:text-[#9aa0a6]">
            New replies use this provider and are billed to its key. Add a key below before you can choose a provider.
          </p>

          <div role="radiogroup" aria-label="Provider in use" className="mt-4 space-y-2">
            {providers.map((status) => {
              const selected = settings?.activeProvider === status.provider;

              return (
                <button
                  key={status.provider}
                  role="radio"
                  aria-checked={selected}
                  disabled={!status.configured || busyProvider !== null}
                  onClick={() => chooseProvider(status.provider)}
                  className={`flex w-full items-center justify-between gap-3 rounded-xl border px-4 py-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                    selected
                      ? "border-[#1a73e8] dark:border-[#8ab4f8] ring-1 ring-[#1a73e8] dark:ring-[#8ab4f8] bg-[#f1f3f4] dark:bg-[#303134]"
                      : "border-[#dadce0] dark:border-[#3c4043] hover:bg-[#f1f3f4] dark:hover:bg-[#353638]"
                  }`}
                >
                  <span>
                    <span className="block text-sm font-medium">{labelFor(status.provider)}</span>
                    <span className="block text-xs text-[#5f6368] dark:text-[#9aa0a6]">
                      {status.configured ? `Key ending ${status.last4}` : "No key saved"}
                    </span>
                  </span>
                  {selected && <Check className="w-4 h-4 text-[#1a73e8] dark:text-[#8ab4f8]" />}
                </button>
              );
            })}
          </div>
        </section>

        <section>
          <h2 className="text-base font-semibold">API keys</h2>
          <p className="mt-1 text-sm text-[#5f6368] dark:text-[#9aa0a6]">
            Keys are stored encrypted and are never shown again. Enter a new key to replace one.
          </p>

          <div className="mt-4 space-y-4">
            {providers.map((status) => {
              const label = labelFor(status.provider);
              const draft = drafts[status.provider] ?? "";

              return (
                <div
                  key={status.provider}
                  className="rounded-xl border border-[#dadce0] dark:border-[#3c4043] bg-white dark:bg-[#1e1f20] p-4"
                >
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold">{label}</h3>
                    <span className="text-xs text-[#5f6368] dark:text-[#9aa0a6]">
                      {status.configured ? `Saved key ending ${status.last4}` : "No key saved"}
                    </span>
                  </div>

                  <div className="mt-3 flex gap-2">
                    <input
                      type="password"
                      autoComplete="off"
                      spellCheck={false}
                      aria-label={`${label} API key`}
                      placeholder={status.configured ? "Enter a new key to replace it" : "Paste your API key"}
                      value={draft}
                      onChange={(event) => setDrafts((current) => ({ ...current, [status.provider]: event.target.value }))}
                      className="min-w-0 flex-1 rounded-lg border border-[#dadce0] dark:border-[#3c4043] bg-white dark:bg-[#131314] px-3 py-2 text-sm text-[#202124] dark:text-[#e3e3e3] placeholder:text-[#80868b] dark:placeholder:text-[#9aa0a6] focus:outline-none focus:ring-2 focus:ring-[#1a73e8]/40"
                    />
                    <button
                      onClick={() => saveKey(status.provider)}
                      disabled={busyProvider !== null || !draft.trim()}
                      className="px-3 py-2 rounded-full text-sm font-medium text-[#1a73e8] dark:text-[#8ab4f8] hover:bg-[#f1f3f4] dark:hover:bg-[#353638] disabled:opacity-40"
                    >
                      Save
                    </button>
                  </div>

                  {errors[status.provider] && (
                    <p className="mt-2 text-xs text-red-600 dark:text-red-400">{errors[status.provider]}</p>
                  )}

                  {status.configured && (
                    <button
                      onClick={() => setPendingDelete(status.provider)}
                      disabled={busyProvider !== null}
                      className="mt-3 text-xs font-medium text-red-600 dark:text-red-400 hover:underline disabled:opacity-40"
                    >
                      Delete key
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      </main>

      {pendingDelete && (
        <ConfirmModal
          heading={`Delete the ${labelFor(pendingDelete)} key?`}
          message="You will need to enter it again to use this provider. If it is the provider in use, no provider will be selected until you choose one."
          confirmLabel="Delete key"
          onCancel={() => setPendingDelete(null)}
          onConfirm={() => deleteKey(pendingDelete)}
        />
      )}
    </div>
  );
};

export default SettingsPage;
