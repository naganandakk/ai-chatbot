import { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { EllipsisVertical, Pause, Play, Volume2 } from 'lucide-react';

interface MoreOptionsBtnProps {
  model: string;
  content: string;
}

type PlaybackState = 'idle' | 'playing' | 'paused';

// Only one message is read aloud at a time, so starting another one stops the current one
let stopActivePlayback: (() => void) | null = null;

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

const MoreOptionsBtn = ({ model, content }: MoreOptionsBtnProps) => {
  const [showMenu, setShowMenu] = useState(false);
  const [isAbove, setIsAbove] = useState(false);
  const [playback, setPlayback] = useState<PlaybackState>('idle');
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
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
    if (utteranceRef.current) {
      utteranceRef.current = null;
      window.speechSynthesis.cancel();
    }
  }, []);

  const stopPlayback = () => {
    utteranceRef.current = null;
    window.speechSynthesis.cancel();
    setPlayback('idle');
  };

  // Some browsers stay paused after cancel(), which would leave the next message silent
  const clearPausedSpeech = () => {
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
    }
  };

  const handleListen = () => {
    if (playback === 'playing') {
      window.speechSynthesis.pause();
      setPlayback('paused');
      return;
    }

    if (playback === 'paused') {
      window.speechSynthesis.resume();
      setPlayback('playing');
      return;
    }

    // Stops whichever message is playing so only the clicked message is read
    stopActivePlayback?.();
    clearPausedSpeech();

    const utterance = new SpeechSynthesisUtterance(toSpeechText(content));
    const finish = () => {
      if (utteranceRef.current === utterance) {
        utteranceRef.current = null;
        setPlayback('idle');
      }
    };
    utterance.onend = finish;
    utterance.onerror = finish;

    utteranceRef.current = utterance;
    stopActivePlayback = stopPlayback;
    window.speechSynthesis.speak(utterance);
    setPlayback('playing');
  };

  const handleButtonClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowMenu(prev => !prev);
  };

  const listenLabel = { idle: 'Listen', playing: 'Pause', paused: 'Resume' }[playback];
  const ListenIcon = { idle: Volume2, playing: Pause, paused: Play }[playback];

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
        className="bg-gray-100 hover:bg-gray-200 text-gray-800 p-1.5 rounded-lg transition-colors flex items-center"
      >
        <EllipsisVertical className="w-4 h-4" />
      </button>

      {showMenu && (
        <div
          ref={menuRef}
          className={`absolute left-0 z-50 w-56 bg-white border border-gray-200 rounded-lg shadow-xl ${
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
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-800 hover:bg-gray-100 rounded-t-lg"
              >
                <ListenIcon className="w-4 h-4" />
                {listenLabel}
              </button>
            </li>
          </ul>
          <div className="px-3 py-2 text-xs text-gray-500 border-t border-gray-200">
            Used <span className="font-medium text-gray-800 break-all">{model || 'Unknown'}</span> model
          </div>
        </div>
      )}
    </div>
  );
};

export default MoreOptionsBtn;
