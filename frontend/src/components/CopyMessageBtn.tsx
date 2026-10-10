// CopyMessageBtn.tsx
import { useEffect, useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { useAppContext } from '../Context';
import { writeClipboard } from '../clipboard';

const HIDE_AFTER_MS = 5000;

interface CopyMessageBtnProps {
  text: string;
  onHide: () => void;
}

const CopyMessageBtn = ({ text, onHide }: CopyMessageBtnProps) => {
  const { notifyError } = useAppContext();
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    if (!copied) {
      return;
    }

    const timer = setTimeout(onHide, HIDE_AFTER_MS);
    return () => clearTimeout(timer);
  }, [copied, onHide]);

  const handleCopy = async () => {
    try {
      await writeClipboard(text);
      setCopied(true);
    } catch (err) {
      console.error('Failed to copy message: ', err);
      notifyError('Could not copy the message.');
    }
  };

  const Icon = copied ? Check : Copy;

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label="Copy message"
      title="Copy message"
      className={`mt-2 p-1.5 rounded-lg transition-colors flex items-center flex-shrink-0 ${
        copied
          ? 'bg-emerald-100 text-emerald-600'
          : 'bg-gray-100 hover:bg-gray-200 text-gray-800'
      }`}
    >
      <Icon className="w-4 h-4" />
    </button>
  );
};

export default CopyMessageBtn;
