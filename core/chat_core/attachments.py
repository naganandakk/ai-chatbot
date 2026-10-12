import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePath

from .models import Attachment
from .settings import positive_int_from_env

MB = 1024 * 1024

DEFAULT_MAX_FILE_MB = 5
DEFAULT_MAX_FILES = 5
DEFAULT_MAX_TOTAL_MB = 10
DEFAULT_MAX_SESSION_MB = 20
# Room for the text fields and multipart framing on top of the file bytes
REQUEST_OVERHEAD_BYTES = MB

IMAGE_SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
]
PDF_MEDIA_TYPE = "application/pdf"
TEXT_MEDIA_TYPE = "text/plain"
TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".log", ".html",
    ".css", ".js", ".jsx", ".ts", ".tsx", ".py", ".java", ".go", ".rs", ".rb", ".php",
    ".c", ".h", ".cpp", ".sql", ".sh",
}
# Sent to the file picker, so the browser only offers what the server accepts
ACCEPTED_EXTENSIONS = sorted(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", *TEXT_EXTENSIONS}
)


@dataclass(frozen=True)
class UploadedFile:
    filename: str
    data: bytes


@dataclass(frozen=True)
class AttachmentLimits:
    max_file_bytes: int = DEFAULT_MAX_FILE_MB * MB
    max_files: int = DEFAULT_MAX_FILES
    max_total_bytes: int = DEFAULT_MAX_TOTAL_MB * MB
    max_session_bytes: int = DEFAULT_MAX_SESSION_MB * MB

    @property
    def max_request_bytes(self) -> int:
        return self.max_total_bytes + REQUEST_OVERHEAD_BYTES

    @classmethod
    def from_env(cls) -> "AttachmentLimits":
        return cls(
            max_file_bytes=positive_int_from_env("MAX_ATTACHMENT_MB", DEFAULT_MAX_FILE_MB) * MB,
            max_files=positive_int_from_env("MAX_ATTACHMENTS_PER_MESSAGE", DEFAULT_MAX_FILES),
            max_total_bytes=positive_int_from_env(
                "MAX_ATTACHMENTS_TOTAL_MB", DEFAULT_MAX_TOTAL_MB
            ) * MB,
            max_session_bytes=positive_int_from_env(
                "MAX_SESSION_ATTACHMENTS_MB", DEFAULT_MAX_SESSION_MB
            ) * MB,
        )

    def to_dict(self) -> dict:
        return {
            "maxFileBytes": self.max_file_bytes,
            "maxFiles": self.max_files,
            "maxTotalBytes": self.max_total_bytes,
            "maxSessionBytes": self.max_session_bytes,
            "acceptedExtensions": ACCEPTED_EXTENSIONS,
        }


def prepare_attachments(
    files: Sequence[UploadedFile],
    limits: AttachmentLimits,
    existing_bytes: int,
) -> list[Attachment]:
    # Checks every upload before anything is saved, so a rejected message leaves no trace.
    if not files:
        return []

    if len(files) > limits.max_files:
        raise ValueError(f"You can attach up to {limits.max_files} files to one message.")

    attachments = []
    total = 0
    for file in files:
        name = clean_filename(file.filename)
        size = len(file.data)

        if size == 0:
            raise ValueError(f"{name} is empty.")
        if size > limits.max_file_bytes:
            raise ValueError(f"{name} is larger than {limits.max_file_bytes // MB} MB.")

        media_type = detect_media_type(name, file.data)
        if media_type is None:
            raise ValueError(
                f"{name} is not a supported file. Attach images (PNG, JPEG, GIF, WebP), "
                "PDFs, or text files."
            )

        total += size
        attachments.append(Attachment(filename=name, media_type=media_type, size=size, data=file.data))

    if total > limits.max_total_bytes:
        raise ValueError(
            f"Files in one message can total at most {limits.max_total_bytes // MB} MB."
        )

    if existing_bytes + total > limits.max_session_bytes:
        raise ValueError(
            f"This chat has reached its {limits.max_session_bytes // MB} MB attachment limit. "
            "Start a new chat to attach more files."
        )

    return attachments


def detect_media_type(filename: str, data: bytes) -> str | None:
    # Judged from the file's bytes, not the browser's MIME type, which the client controls
    for signature, media_type in IMAGE_SIGNATURES:
        if data.startswith(signature):
            return media_type
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return PDF_MEDIA_TYPE
    if PurePath(filename).suffix.lower() in TEXT_EXTENSIONS and _is_text(data):
        return TEXT_MEDIA_TYPE
    return None


def attachment_block(attachment: Attachment) -> dict:
    # Provider-neutral content block. Each provider converts it to its own wire format.
    if attachment.media_type == TEXT_MEDIA_TYPE:
        text = attachment.data.decode("utf-8")
        return {
            "type": "text",
            "text": f'<file name="{attachment.filename}">\n{text}\n</file>',
        }

    kind = "image" if attachment.media_type.startswith("image/") else "document"
    return {
        "type": kind,
        "filename": attachment.filename,
        "media_type": attachment.media_type,
        "data": attachment.data,
    }


def clean_filename(raw: str) -> str:
    # Keeps only the base name, and drops characters that would break a quoted header or tag
    base = re.split(r"[\\/]", raw or "")[-1]
    cleaned = re.sub(r'[\x00-\x1f"<>]', "", base).strip()
    return cleaned[:255] or "file"


def format_mb(size_bytes: int) -> str:
    return f"{size_bytes // MB} MB"


def _is_text(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True
