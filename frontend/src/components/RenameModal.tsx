import { useEffect, useState, type FormEvent } from 'react';
import { createPortal } from 'react-dom';

interface RenameModalProps {
  initialTitle: string;
  onCancel: () => void;
  onSave: (title: string) => void;
}

// Asks for a new chat name. Escape or a tap outside cancels, like the other dialogs
const RenameModal = ({ initialTitle, onCancel, onSave }: RenameModalProps) => {
  const [title, setTitle] = useState(initialTitle);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onCancel();
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onCancel]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSave(title);
  };

  return createPortal(
    <div
      onClick={onCancel}
      className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/40 sm:p-4"
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="rename-modal-heading"
        onSubmit={handleSubmit}
        onClick={e => e.stopPropagation()}
        className="w-full sm:max-w-sm bg-white dark:bg-[#28292a] text-[#202124] dark:text-[#e3e3e3] rounded-t-2xl sm:rounded-2xl shadow-xl border border-[#dadce0] dark:border-[#3c4043] p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))]"
      >
        <div className="w-10 h-1 mx-auto mb-4 rounded-full bg-[#dadce0] dark:bg-[#5f6368] sm:hidden" />
        <h2 id="rename-modal-heading" className="text-base font-bold">Rename chat</h2>
        <input
          type="text"
          aria-label="Chat name"
          autoFocus
          value={title}
          onChange={e => setTitle(e.target.value)}
          className="mt-4 w-full bg-white dark:bg-[#131314] text-[#202124] dark:text-white px-3 py-2 rounded-lg text-sm border border-[#1a73e8] focus:outline-none"
        />

        <div className="mt-6 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="w-full sm:w-auto px-4 py-2 rounded-full text-sm font-medium text-[#1a73e8] dark:text-[#8ab4f8] hover:bg-[#f1f3f4] dark:hover:bg-[#353638]"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!title.trim()}
            className="w-full sm:w-auto px-4 py-2 rounded-full text-sm font-medium text-white bg-[#1a73e8] hover:bg-[#1765cc] disabled:opacity-50"
          >
            Save
          </button>
        </div>
      </form>
    </div>,
    document.body,
  );
};

export default RenameModal;
