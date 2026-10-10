// CopyResponseBtn.tsx
import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { useAppContext } from '../Context';
import { writeClipboard } from '../clipboard';

const BLOCK_TAGS = new Set(['P', 'DIV', 'LI', 'H1', 'H2', 'H3', 'PRE', 'TR', 'UL', 'OL', 'TABLE']);

// Collects the text a user sees, skipping buttons such as the code block "Copy" labels
const getRenderedText = (node: Node): string => {
  if (node.nodeType === Node.TEXT_NODE) {
    return node.textContent ?? '';
  }

  if (!(node instanceof HTMLElement) || node.tagName === 'BUTTON') {
    return '';
  }

  if (node.tagName === 'BR') {
    return '\n';
  }

  const text = Array.from(node.childNodes).map(getRenderedText).join('');

  if (node.tagName === 'TD' || node.tagName === 'TH') {
    return `${text}\t`;
  }

  return BLOCK_TAGS.has(node.tagName) ? `${text}\n` : text;
};

// Tailwind classes do not survive a paste, so the copied HTML carries inline styles
const PRE_STYLE = {
  backgroundColor: '#18181b',
  color: '#f4f4f5',
  padding: '10px',
  borderRadius: '8px',
  fontFamily: 'monospace',
  fontSize: '13px',
  whiteSpace: 'pre-wrap',
};
const INLINE_CODE_STYLE = {
  fontFamily: 'monospace',
  backgroundColor: '#f4f4f5',
  padding: '1px 4px',
  borderRadius: '4px',
};
const HEADING_STYLES: Record<string, Partial<CSSStyleDeclaration>> = {
  H1: { fontSize: '20px', fontWeight: '600' },
  H2: { fontSize: '18px', fontWeight: '600' },
  H3: { fontSize: '16px', fontWeight: '600' },
};
const CELL_STYLE = {
  border: '1px solid #e4e4e7',
  padding: '6px 12px',
  textAlign: 'left',
};

// Builds the HTML version of the response with inline styles for the parts that lose their look
const getRichHtml = (target: HTMLElement): string => {
  const clone = target.cloneNode(true) as HTMLElement;

  clone.querySelectorAll('button').forEach((button) => button.remove());
  clone.querySelectorAll<HTMLElement>('pre').forEach((pre) => Object.assign(pre.style, PRE_STYLE));
  clone.querySelectorAll<HTMLElement>('code').forEach((code) => {
    if (!code.closest('pre')) {
      Object.assign(code.style, INLINE_CODE_STYLE);
    }
  });
  clone.querySelectorAll<HTMLElement>('h1, h2, h3').forEach((heading) => {
    Object.assign(heading.style, HEADING_STYLES[heading.tagName]);
  });
  clone.querySelectorAll<HTMLElement>('table').forEach((table) => {
    table.style.borderCollapse = 'collapse';
  });
  clone.querySelectorAll<HTMLElement>('th, td').forEach((cell) => Object.assign(cell.style, CELL_STYLE));

  return clone.innerHTML;
};

interface CopyResponseBtnProps {
  targetId: string;
}

const CopyResponseBtn = ({ targetId }: CopyResponseBtnProps) => {
  const { triggerError } = useAppContext();
  const [copied, setCopied] = useState<boolean>(false);

  const handleCopy = async () => {
    const target = document.getElementById(targetId);

    if (!target) {
      return;
    }

    const text = getRenderedText(target).replace(/\n{3,}/g, '\n\n').trim();
    const html = getRichHtml(target);

    try {
      if (navigator.clipboard?.write && 'ClipboardItem' in window) {
        await navigator.clipboard.write([
          new ClipboardItem({
            'text/html': new Blob([html], { type: 'text/html' }),
            'text/plain': new Blob([text], { type: 'text/plain' }),
          }),
        ]);
      } else {
        await writeClipboard(text);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy response: ', err);
      triggerError('Could not copy the response.');
    }
  };

  const Icon = copied ? Check : Copy;

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label="Copy response"
      title="Copy response"
      className={`p-1.5 rounded-lg transition-colors flex items-center ${
        copied
          ? 'bg-emerald-100 text-emerald-600'
          : 'bg-gray-100 hover:bg-gray-200 text-gray-800'
      }`}
    >
      <Icon className="w-4 h-4" />
    </button>
  );
};

export default CopyResponseBtn;
