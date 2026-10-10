// CopyContentBtn.tsx
import React, { useState } from 'react';
import { writeClipboard } from '../clipboard';

interface CopyContentBtnProps {
  children: React.ReactNode;
}

const CopyContentBtn = ({ children }: CopyContentBtnProps) => {
  const [copied, setCopied] = useState<boolean>(false);

  const handleCopy = async () => {
    // Safely extract the code text from children
    const childProps = (children as React.ReactElement)?.props;
    const textToCopy = childProps?.children || '';

    try {
      await writeClipboard(String(textToCopy));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className={`absolute top-2 right-2 px-2 py-1 text-xs font-medium rounded border transition-all duration-200 z-10
        ${copied
          ? 'bg-emerald-600/20 text-emerald-400 border-emerald-500/30'
          : 'bg-zinc-800 text-zinc-400 border-zinc-700 hover:bg-zinc-700 hover:text-zinc-200'
        }`}
    >
      {copied ? 'Copied!' : 'Copy'}
    </button>
  );
}

export default CopyContentBtn;
