import { useEffect, useRef, useState } from 'react';
import { useAppContext } from '../Context';
import { formatCacheHit, formatCost, formatCostShort } from '../format';

// Shows the active session's token and cost totals, with a breakdown on click
const SessionUsage = () => {
  const { activeSession } = useAppContext();
  const [showDetails, setShowDetails] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: PointerEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setShowDetails(false);
      }
    };

    if (showDetails) {
      document.addEventListener('pointerdown', handleClickOutside, true);
    }

    return () => {
      document.removeEventListener('pointerdown', handleClickOutside, true);
    };
  }, [showDetails]);

  const usage = activeSession?.usage;
  const replies = (usage?.pricedMessages ?? 0) + (usage?.unpricedMessages ?? 0);

  // Stays hidden until a reply has reported its tokens
  if (!usage || replies === 0) {
    return null;
  }

  const totalTokens = usage.inputTokens + usage.outputTokens;
  const costLabel = usage.costUsd === null ? null : formatCostShort(usage.costUsd);
  const tokenLabel = `${totalTokens.toLocaleString()} tokens`;
  const cacheHit = formatCacheHit(usage.cacheReadTokens, usage.inputTokens);

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setShowDetails(prev => !prev)}
        aria-expanded={showDetails}
        title="Session usage"
        className="rounded-lg px-2 py-1.5 text-sm text-[#5f6368] dark:text-[#9aa0a6] hover:bg-[#e8eaed] dark:hover:bg-[#303134] transition-all"
      >
        {/* Phones have little header space, so only the cost shows there when it is known */}
        {costLabel && <span>{costLabel}</span>}
        <span className={costLabel ? 'hidden md:inline' : undefined}>
          {costLabel && ' · '}{tokenLabel}
        </span>
      </button>

      {showDetails && (
        <div className="fixed right-4 top-14 w-max max-w-[calc(100vw-2rem)] md:absolute md:right-0 md:top-full md:mt-2 md:w-60 z-50 bg-white dark:bg-[#28292a] border border-gray-200 dark:border-[#3c4043] rounded-lg shadow-xl px-3 py-2 text-xs text-gray-500 dark:text-[#9aa0a6]">
          <div className="font-medium text-gray-800 dark:text-[#e3e3e3] text-sm">Session usage</div>
          <div className="mt-1 space-y-0.5">
            <div>Replies: <span className="font-medium text-gray-800 dark:text-[#e3e3e3]">{replies.toLocaleString()}</span></div>
            <div>Input tokens: <span className="font-medium text-gray-800 dark:text-[#e3e3e3]">{usage.inputTokens.toLocaleString()}</span></div>
            <div>Output tokens: <span className="font-medium text-gray-800 dark:text-[#e3e3e3]">{usage.outputTokens.toLocaleString()}</span></div>
            <div>Cost: <span className="font-medium text-gray-800 dark:text-[#e3e3e3]">{usage.costUsd === null ? 'Unavailable' : formatCost(usage.costUsd)}</span></div>
            {usage.cacheReadTokens > 0 && (
              <div>
                Cache hits: <span className="font-medium text-gray-800 dark:text-[#e3e3e3]">{usage.cacheReadTokens.toLocaleString()}</span>
                {cacheHit && <span> ({cacheHit} of input)</span>}
              </div>
            )}
            {usage.cacheWriteTokens > 0 && (
              <div>Cache writes: <span className="font-medium text-gray-800 dark:text-[#e3e3e3]">{usage.cacheWriteTokens.toLocaleString()}</span></div>
            )}
          </div>
          {usage.unpricedMessages > 0 && (
            <div className="mt-1 text-amber-700 dark:text-amber-400">
              {usage.unpricedMessages === 1
                ? '1 reply has no known price, so the cost is partial'
                : `${usage.unpricedMessages} replies have no known price, so the cost is partial`}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SessionUsage;
