import type { AttachmentLimits } from "./api";

const MB = 1024 * 1024;

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < MB) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${(bytes / MB).toFixed(1)} MB`;
}

// Checks the files added to a prompt against the server's limits. Returns the first problem,
// or null when the files fit. The server checks again, so this only saves a round trip.
export function checkAttachments(
  incoming: File[],
  current: File[],
  limits: AttachmentLimits,
): string | null {
  const all = [...current, ...incoming];

  if (all.length > limits.maxFiles) {
    return `You can attach up to ${limits.maxFiles} files to one message.`;
  }

  for (const file of incoming) {
    const dot = file.name.lastIndexOf(".");
    const extension = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
    if (!limits.acceptedExtensions.includes(extension)) {
      return `${file.name} is not a supported file. Attach images (PNG, JPEG, GIF, WebP), PDFs, or text files.`;
    }
    if (file.size === 0) {
      return `${file.name} is empty.`;
    }
    if (file.size > limits.maxFileBytes) {
      return `${file.name} is larger than ${formatFileSize(limits.maxFileBytes)}.`;
    }
  }

  const total = all.reduce((sum, file) => sum + file.size, 0);
  if (total > limits.maxTotalBytes) {
    return `Files in one message can total at most ${formatFileSize(limits.maxTotalBytes)}.`;
  }

  return null;
}
