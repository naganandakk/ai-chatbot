import { useEffect, useRef, useState } from 'react';
import { Edit2, MoreVertical, RotateCcw, Trash2 } from 'lucide-react';
import { useAppContext } from '../Context';
import { useSessionActions } from '../useSessionActions';
import ConfirmModal from './ConfirmModal';
import RenameModal from './RenameModal';

type PendingAction = 'rename' | 'clear' | 'delete';

// Phone header menu for the active session. Desktop uses the sidebar's menu instead.
const SessionMenu = () => {
  const { activeSession, isGenerating } = useAppContext();
  const { deleteChat, clearChat, renameChat } = useSessionActions();
  const [showMenu, setShowMenu] = useState(false);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

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

  if (!activeSession) {
    return null;
  }

  const sessionId = activeSession.id;
  const chooseAction = (action: PendingAction) => {
    setShowMenu(false);
    setPendingAction(action);
  };
  const finishAction = () => setPendingAction(null);

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setShowMenu(prev => !prev)}
        disabled={isGenerating}
        aria-label="Session options"
        aria-expanded={showMenu}
        title="Session options"
        className="p-2 rounded-full text-[#5f6368] dark:text-[#9aa0a6] hover:bg-[#e8eaed] dark:hover:bg-[#303134] disabled:opacity-60 transition-all"
      >
        <MoreVertical className="w-5 h-5" />
      </button>

      {showMenu && (
        <div className="absolute right-0 top-full mt-2 z-50 w-48 bg-white dark:bg-[#28292a] border border-[#dadce0] dark:border-[#3c4043] rounded-lg shadow-lg py-1">
          <button type="button" onClick={() => chooseAction('rename')} className="flex items-center gap-2.5 w-full px-4 py-2 text-sm text-[#3c4043] dark:text-[#e3e3e3] hover:bg-[#f1f3f4] dark:hover:bg-[#353638]">
            <Edit2 className="w-4 h-4" /> Rename
          </button>
          <button type="button" onClick={() => chooseAction('clear')} className="flex items-center gap-2.5 w-full px-4 py-2 text-sm text-[#3c4043] dark:text-[#e3e3e3] hover:bg-[#f1f3f4] dark:hover:bg-[#353638]">
            <RotateCcw className="w-4 h-4" /> Clear history
          </button>
          <button type="button" onClick={() => chooseAction('delete')} className="flex items-center gap-2.5 w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-[#353638]">
            <Trash2 className="w-4 h-4" /> Delete
          </button>
        </div>
      )}

      {pendingAction === 'rename' && (
        <RenameModal
          initialTitle={activeSession.title}
          onCancel={finishAction}
          onSave={(title) => {
            void renameChat(sessionId, title);
            finishAction();
          }}
        />
      )}

      {pendingAction === 'clear' && (
        <ConfirmModal
          heading="Clear chat history?"
          message={<>
            All messages in <span className="font-medium text-[#3c4043] dark:text-[#c4c7c5]">&ldquo;{activeSession.title}&rdquo;</span> will be removed. The chat itself will be kept. This can&apos;t be undone.
          </>}
          confirmLabel="Clear"
          onCancel={finishAction}
          onConfirm={() => {
            void clearChat(sessionId);
            finishAction();
          }}
        />
      )}

      {pendingAction === 'delete' && (
        <ConfirmModal
          heading="Delete chat?"
          message={<>
            <span className="font-medium text-[#3c4043] dark:text-[#c4c7c5]">&ldquo;{activeSession.title}&rdquo;</span> will be permanently deleted. This can&apos;t be undone.
          </>}
          confirmLabel="Delete"
          onCancel={finishAction}
          onConfirm={() => {
            void deleteChat(sessionId);
            finishAction();
          }}
        />
      )}
    </div>
  );
};

export default SessionMenu;
