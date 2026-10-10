import { useEffect, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

interface ConfirmModalProps {
  heading: string;
  message: ReactNode;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: () => void;
}

// Rendered through a portal so the sidebar's overflow and outside-click handling don't affect it
const ConfirmModal = ({ heading, message, confirmLabel, onCancel, onConfirm }: ConfirmModalProps) => {
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

  return createPortal(
    <div
      onClick={onCancel}
      className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/40 sm:p-4"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-heading"
        onClick={e => e.stopPropagation()}
        className="w-full sm:max-w-sm bg-white dark:bg-[#28292a] text-[#202124] dark:text-[#e3e3e3] rounded-t-2xl sm:rounded-2xl shadow-xl border border-[#dadce0] dark:border-[#3c4043] p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))]"
      >
        <div className="w-10 h-1 mx-auto mb-4 rounded-full bg-[#dadce0] dark:bg-[#5f6368] sm:hidden" />
        <h2 id="confirm-modal-heading" className="text-base font-bold">{heading}</h2>
        <p className="mt-2 text-sm text-[#5f6368] dark:text-[#9aa0a6] break-words">{message}</p>

        <div className="mt-6 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
          <button
            autoFocus
            onClick={onCancel}
            className="w-full sm:w-auto px-4 py-2 rounded-full text-sm font-medium text-[#1a73e8] dark:text-[#8ab4f8] hover:bg-[#f1f3f4] dark:hover:bg-[#353638]"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="w-full sm:w-auto px-4 py-2 rounded-full text-sm font-medium text-white bg-red-600 hover:bg-red-700"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
};

export default ConfirmModal;
