import { FileText } from 'lucide-react';
import { attachmentUrl, type Attachment } from "../api";
import { formatFileSize } from "../attachments";

const chipClass = "flex items-center gap-2 max-w-full rounded-xl border border-[#dadce0] dark:border-[#3c4043] bg-white dark:bg-[#303134] px-3 py-2 text-xs text-[#202124] dark:text-[#e3e3e3]";

// Files sent with a message. Images preview inline, other files link to download.
const MessageAttachments = ({ attachments }: { attachments: Attachment[] }) => (
  <ul aria-label="Attached files" className="flex flex-wrap gap-2 pb-2">
    {attachments.map((attachment, index) => {
      const key = attachment.id || `${attachment.filename}-${index}`;
      // Files still in the prompt have no id yet, so they cannot link anywhere
      const url = attachment.id ? attachmentUrl(attachment.id) : null;
      // The bubble toggles its copy button on click, so link clicks stop there
      const stop = (e: React.MouseEvent) => e.stopPropagation();

      if (url && attachment.mediaType.startsWith("image/")) {
        return (
          <li key={key}>
            <a href={url} target="_blank" rel="noreferrer" onClick={stop} title={attachment.filename} className="block">
              <img src={url} alt={attachment.filename} className="max-h-48 max-w-[16rem] rounded-xl border border-[#dadce0] dark:border-[#3c4043] object-cover" />
            </a>
          </li>
        );
      }

      const content = (
        <>
          <FileText className="w-4 h-4 shrink-0 text-[#5f6368] dark:text-[#9aa0a6]" />
          <span className="truncate max-w-[12rem]">{attachment.filename}</span>
          <span className="shrink-0 text-[#5f6368] dark:text-[#9aa0a6]">{formatFileSize(attachment.size)}</span>
        </>
      );

      return (
        <li key={key}>
          {url ? (
            <a href={url} download={attachment.filename} onClick={stop} className={`${chipClass} hover:bg-[#e8eaed] dark:hover:bg-[#3c4043] transition-colors`}>
              {content}
            </a>
          ) : (
            <span className={chipClass}>{content}</span>
          )}
        </li>
      );
    })}
  </ul>
);

export default MessageAttachments;
