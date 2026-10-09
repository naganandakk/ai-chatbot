import { useState, useRef, useEffect } from 'react';
import type { Source } from '../api';

interface SourcesBtnProps {
  sources: Source[];
  id: number;
}

const SourcesBtn = ({ sources, id }: SourcesBtnProps) => {
  const [showSources, setShowSources] = useState(false);
  const [isAbove, setIsAbove] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: PointerEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setShowSources(false);
      }
    };

    if (showSources) {
      document.addEventListener('pointerdown', handleClickOutside, true);
    }

    return () => {
      document.removeEventListener('pointerdown', handleClickOutside, true);
    };
  }, [showSources]);

  useEffect(() => {
    const button = buttonRef.current;
    const tooltip = tooltipRef.current;

    if (showSources && tooltip && button) {
      setTimeout(() => {
        const buttonRect = button.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();

        const spaceBelow = window.innerHeight - buttonRect.bottom;
        const spaceAbove = buttonRect.top;
        const tooltipHeight = tooltipRect.height;
        const minGap = 20;

        if (spaceBelow < tooltipHeight + minGap && spaceAbove > tooltipHeight + minGap) {
          setIsAbove(true);
        } else {
          setIsAbove(false);
        }
      }, 0);
    }
  }, [showSources]);

  const handleButtonClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowSources(prev => !prev);
  };

  const handleCloseClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowSources(false);
  };

  if (!sources || sources.length === 0) {
    return null;
  }

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
        className="bg-gray-100 hover:bg-gray-200 text-gray-800 text-sm font-medium px-2 py-1 rounded-lg transition-colors flex items-center gap-2"
      >
        Sources ({sources.length})
      </button>

      {showSources && (
        <div
          ref={tooltipRef}
          className={`absolute left-0 z-50 w-80 bg-white border border-gray-200 rounded-lg shadow-xl transition-all duration-200 flex flex-col ${
            isAbove
              ? 'bottom-full mb-2'
              : 'top-full mt-2'
          }`}
          onClick={(e) => e.stopPropagation()}
        >
          <div
            className={`absolute left-4 w-3 h-3 bg-white border border-gray-200 transform rotate-45 ${
              isAbove
                ? '-bottom-1.5 border-t-0 border-l-0'
                : '-top-1.5 border-b-0 border-r-0'
            }`}
          />

          <div className="flex-1 overflow-y-auto max-h-80 shadow-xl">
            <ul className="divide-y divide-gray-200">
              {sources.map((source, index) => (
                <li
                  key={`${id}-source-${index}`}
                  className="hover:bg-blue-50 transition-colors"
                >
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block p-3 group"
                  >
                    <p className="text-xs font-medium text-gray-900 group-hover:text-blue-600 line-clamp-2">
                      {source.title || 'Untitled Source'}
                    </p>
                    <p className="text-xs text-gray-500 mt-1 line-clamp-1 break-all">
                      {source.url}
                    </p>
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default SourcesBtn;
