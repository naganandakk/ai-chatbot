import { useEffect, useState } from 'react';
import { api, ModelOption } from "../api";
import { useAppContext } from "../Context";

type LoadStatus = "loading" | "ready" | "error";

// Display names for vendor prefixes in model ids, e.g. "anthropic/claude-haiku-4.5"
const VENDOR_NAMES: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  google: "Google",
  "meta-llama": "Meta",
  mistralai: "Mistral AI",
  "x-ai": "xAI",
  deepseek: "DeepSeek",
  qwen: "Qwen",
};

// Model ids without a prefix (direct Anthropic) belong to the provider the list came from
function vendorOf(model: ModelOption, provider: string): string {
  const prefix = model.id.includes("/") ? model.id.split("/")[0] : provider;
  return VENDOR_NAMES[prefix] ?? prefix.charAt(0).toUpperCase() + prefix.slice(1);
}

// Keeps server order within each group, and groups in the order they first appear
function groupByVendor(models: ModelOption[], provider: string): [string, ModelOption[]][] {
  const groups = new Map<string, ModelOption[]>();

  for (const model of models) {
    const vendor = vendorOf(model, provider);
    groups.set(vendor, [...(groups.get(vendor) ?? []), model]);
  }

  return [...groups.entries()];
}

// OpenRouter names read "Anthropic: Claude Haiku 4.5". The group label already says Anthropic
function displayName(model: ModelOption, vendor: string): string {
  const prefix = `${vendor}: `;
  return model.name.startsWith(prefix) ? model.name.slice(prefix.length) : model.name;
}

const ModelPicker = () => {
  const {
    selectedModel, selectModel,
    isGenerating,
    notifyError
  } = useAppContext();
  const [models, setModels] = useState<ModelOption[]>([]);
  const [provider, setProvider] = useState<string>("");
  const [status, setStatus] = useState<LoadStatus>("loading");

  useEffect(() => {
    let cancelled = false;

    api.listModels()
      .then((list) => {
        if (cancelled) {
          return;
        }

        setModels(list.models);
        setProvider(list.provider);
        setStatus("ready");

        // A saved model the provider no longer offers falls back to the first one
        if (!list.models.some((model) => model.id === selectedModel)) {
          selectModel(list.models[0]?.id ?? "");
        }
      })
      .catch((requestError) => {
        if (cancelled) {
          return;
        }

        setStatus("error");
        notifyError(
          requestError instanceof Error ? requestError.message : "Could not load models",
        );
      });

    return () => {
      cancelled = true;
    };
    // Loads once on mount. The saved selection is read from context at that point
  }, []);

  const placeholder = status === "error" ? "Models unavailable" : "Loading models...";

  return (
    <select
      aria-label="Model"
      value={selectedModel}
      onChange={(e) => selectModel(e.target.value)}
      disabled={isGenerating || status !== "ready"}
      className="max-w-[10rem] truncate rounded-lg bg-transparent px-2 py-1.5 text-sm text-[#202124] dark:text-[#e3e3e3] hover:bg-[#e8eaed] dark:hover:bg-[#303134] disabled:opacity-60 focus:outline-none"
    >
      {status !== "ready" && <option value={selectedModel}>{placeholder}</option>}
      {groupByVendor(models, provider).map(([vendor, group]) => (
        <optgroup key={vendor} label={vendor}>
          {group.map((model) => (
            <option key={model.id} value={model.id}>{displayName(model, vendor)}</option>
          ))}
        </optgroup>
      ))}
    </select>
  );
};

export default ModelPicker;
