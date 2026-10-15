import { Wrench } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api, Tool } from "../api";
import { FRESH_FOR_MS, readCache, writeCache } from "../cache";
import { useAppContext } from "../Context";

// Lists the tools the server offers. Each one stays off until the user switches it on
const ToolsMenu = () => {
  const {
    selectedTools, selectTools,
    isGenerating, isLoadingSession,
    notifyError,
    currentUser,
  } = useAppContext();
  const [tools, setTools] = useState<Tool[]>([]);
  const [showMenu, setShowMenu] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    const userId = currentUser?.id ?? null;

    const showTools = (list: Tool[]) => {
      setTools(list);

      // A saved tool the server no longer offers is dropped, so it cannot block sending
      const known = new Set(list.map((tool) => tool.id));
      const kept = selectedTools.filter((id) => known.has(id));
      if (kept.length !== selectedTools.length) {
        selectTools(kept);
      }
    };

    // The server's tool list is static, so a cached copy is used for a day before asking again
    const cached = userId ? readCache<Tool[]>(userId, "tools") : null;
    if (cached) {
      showTools(cached.data);
      if (cached.ageMs < FRESH_FOR_MS.tools) {
        return;
      }
    }

    api.listTools()
      .then((list) => {
        if (cancelled) {
          return;
        }

        showTools(list);
        if (userId) {
          writeCache(userId, "tools", list);
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          notifyError(
            requestError instanceof Error ? requestError.message : "Could not load tools",
          );
        }
      });

    return () => {
      cancelled = true;
    };
    // Loads once on mount. The saved selection is read from context at that point
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: PointerEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setShowMenu(false);
      }
    };

    if (showMenu) {
      document.addEventListener('pointerdown', handleClickOutside, true);
    }

    return () => {
      document.removeEventListener('pointerdown', handleClickOutside, true);
    };
  }, [showMenu]);

  const toggleTool = (id: string) => {
    selectTools(
      selectedTools.includes(id)
        ? selectedTools.filter((toolId) => toolId !== id)
        : [...selectedTools, id],
    );
  };

  const active = selectedTools.length > 0;

  return (
    <div className="relative shrink-0" ref={containerRef}>
      <button
        type="button"
        onClick={() => setShowMenu((open) => !open)}
        disabled={isGenerating || isLoadingSession || tools.length === 0}
        aria-label="Tools"
        aria-haspopup="menu"
        aria-expanded={showMenu}
        title={active ? `${selectedTools.length} tool${selectedTools.length === 1 ? '' : 's'} on` : "Tools"}
        className={`flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm hover:bg-[#e8eaed] dark:hover:bg-[#303134] transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${active ? 'text-[#1a73e8] dark:text-[#8ab4f8]' : 'text-[#202124] dark:text-[#e3e3e3]'}`}
      >
        <Wrench className="w-4 h-4" />
        {active && <span className="text-xs font-medium">{selectedTools.length}</span>}
      </button>

      {showMenu && (
        <div
          role="menu"
          className="absolute bottom-full right-0 z-50 mb-2 w-64 bg-white dark:bg-[#28292a] border border-gray-200 dark:border-[#3c4043] rounded-lg shadow-xl"
        >
          <ul className="py-1">
            {tools.map((tool) => (
              <li key={tool.id}>
                <label className="flex items-start gap-3 px-3 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-[#353638]">
                  <input
                    type="checkbox"
                    checked={selectedTools.includes(tool.id)}
                    onChange={() => toggleTool(tool.id)}
                    className="mt-1 accent-[#1a73e8] dark:accent-[#8ab4f8]"
                  />
                  <span className="min-w-0">
                    <span className="block text-sm text-gray-800 dark:text-[#e3e3e3]">{tool.name}</span>
                    <span className="block text-xs text-gray-500 dark:text-[#9aa0a6]">{tool.description}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default ToolsMenu;
