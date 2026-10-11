import { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { EllipsisVertical, Pause, Play, Volume2 } from 'lucide-react';
import { speechPlayback, useSpeechPlayback } from '../speech';
import type { Usage } from '../api';
import { formatCost } from '../format';

interface MoreOptionsBtnProps {
  model: string;
  content: string;
  playbackId: string;
  truncated?: boolean;
  usage?: Usage | null;
  durationMs?: number | null;
}

// Removes markdown symbols so the speech engine does not read them out
const toSpeechText = (markdown: string) => markdown
  .replace(/```[\s\S]*?```/g, ' ')
  .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
  .replace(/[*_#>`~]+/g, '');

// The chat list scrolls inside its own container, so the menu must fit within that area, not just the window
const getVisibleBounds = (element: HTMLElement) => {
  let bounds = { top: 0, bottom: window.innerHeight };
  let ancestor = element.parentElement;

  while (ancestor) {
    const { overflowY } = getComputedStyle(ancestor);
    if (['auto', 'scroll', 'hidden'].includes(overflowY)) {
      const rect = ancestor.getBoundingClientRect();
      bounds = {
        top: Math.max(bounds.top, rect.top),
        bottom: Math.min(bounds.bottom, rect.bottom),
      };
      break;
    }
    ancestor = ancestor.parentElement;
  }

  return bounds;
};

const MoreOptionsBtn = ({ model, content, playbackId, truncated, usage, durationMs }: MoreOptionsBtnProps) => {
  const [showMenu, setShowMenu] = useState(false);
  const [isAbove, setIsAbove] = useState(false);
  const playback = useSpeechPlayback();
  const playbackStatus = playback.id === playbackId ? playback.status : 'idle';
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Opens the menu upward when there is not enough room below the button
  useLayoutEffect(() => {
    const button = buttonRef.current;
    const menu = menuRef.current;

    if (showMenu && menu && button) {
      const buttonRect = button.getBoundingClientRect();
      const menuHeight = menu.getBoundingClientRect().height;
      const bounds = getVisibleBounds(button);
      const spaceBelow = bounds.bottom - buttonRect.bottom;
      const spaceAbove = buttonRect.top - bounds.top;
      const minGap = 20;

      setIsAbove(spaceBelow < menuHeight + minGap && spaceAbove > menuHeight + minGap);
    }
  }, [showMenu]);

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

  // Stops speech if this message is removed from the chat while it is playing
  useEffect(() => () => {
    if (speechPlayback.isActive(playbackId)) {
      speechPlayback.stop();
    }
  }, [playbackId]);

  const handleListen = () => {
    setShowMenu(false);

    if (playbackStatus === 'playing') {
      speechPlayback.pause();
    } else if (playbackStatus === 'paused') {
      speechPlayback.resume();
    } else {
      speechPlayback.play(playbackId, toSpeechText(content));
    }
  };

  const handleButtonClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowMenu(prev => !prev);
  };

  const listenLabel = { idle: 'Listen', playing: 'Pause', paused: 'Resume' }[playbackStatus];
  const ListenIcon = { idle: Volume2, playing: Pause, paused: Play }[playbackStatus];

  return (
    <div
      className="relative inline-block"
      ref={containerRef}
      onClick={(e) => e.stopPropagation()}
    >
      <button
        ref={buttonRef}
        onClick={handleButtonClick}
        type="button"
        aria-label="More options"
        title="More options"
        className="bg-gray-100 hover:bg-gray-200 text-gray-800 dark:bg-[#303134] dark:hover:bg-[#3c4043] dark:text-[#e3e3e3] p-1.5 rounded-lg transition-colors flex items-center"
      >
        <EllipsisVertical className="w-4 h-4" />
      </button>

      {showMenu && (
        <div
          ref={menuRef}
          className={`absolute left-0 z-50 w-56 bg-white dark:bg-[#28292a] border border-gray-200 dark:border-[#3c4043] rounded-lg shadow-xl ${
            isAbove
              ? 'bottom-full mb-2'
              : 'top-full mt-2'
          }`}
        >
          <ul>
            <li>
              <button
                type="button"
                onClick={handleListen}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-800 dark:text-[#e3e3e3] hover:bg-gray-100 dark:hover:bg-[#353638] rounded-t-lg"
              >
                <ListenIcon className="w-4 h-4" />
                {listenLabel}
              </button>
            </li>
          </ul>
          <div className="px-3 py-2 text-xs text-gray-500 dark:text-[#9aa0a6] border-t border-gray-200 dark:border-[#3c4043]">
            Used <span className="font-medium text-gray-800 dark:text-[#e3e3e3] break-all">{model || 'Unknown'}</span> model
            {durationMs != null && (
              <div className="mt-1">Time taken: <span className="font-medium text-gray-800 dark:text-[#e3e3e3]">{(durationMs / 1000).toFixed(1)} s</span></div>
            )}
            {usage && (
              <div className="mt-1 space-y-0.5">
                <div>Input tokens: <span className="font-medium text-gray-800 dark:text-[#e3e3e3]">{usage.inputTokens.toLocaleString()}</span></div>
                <div>Output tokens: <span className="font-medium text-gray-800 dark:text-[#e3e3e3]">{usage.outputTokens.toLocaleString()}</span></div>
                <div>Cost: <span className="font-medium text-gray-800 dark:text-[#e3e3e3]">{usage.costUsd === null ? 'Unavailable' : formatCost(usage.costUsd)}</span></div>
              </div>
            )}
            {truncated && (
              <div className="mt-1 text-amber-700 dark:text-amber-400">Reply stopped at the length limit</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default MoreOptionsBtn;
