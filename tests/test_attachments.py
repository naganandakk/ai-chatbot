import pytest

from core.chat_core.attachments import (
    MB,
    AttachmentLimits,
    UploadedFile,
    clean_filename,
    detect_media_type,
    prepare_attachments,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16
PDF = b"%PDF-1.7\n" + b"0" * 16


def test_limits_default_to_five_mb_per_file_and_ten_mb_per_message():
    limits = AttachmentLimits()

    assert limits.max_file_bytes == 5 * MB
    assert limits.max_files == 5
    assert limits.max_total_bytes == 10 * MB
    assert limits.max_session_bytes == 20 * MB


def test_limits_read_from_env(monkeypatch):
    monkeypatch.setenv("MAX_ATTACHMENT_MB", "2")
    monkeypatch.setenv("MAX_ATTACHMENTS_PER_MESSAGE", "3")
    monkeypatch.setenv("MAX_ATTACHMENTS_TOTAL_MB", "4")
    monkeypatch.setenv("MAX_SESSION_ATTACHMENTS_MB", "8")

    limits = AttachmentLimits.from_env()

    assert (limits.max_file_bytes, limits.max_files) == (2 * MB, 3)
    assert (limits.max_total_bytes, limits.max_session_bytes) == (4 * MB, 8 * MB)


@pytest.mark.parametrize("raw", ["0", "-1", "lots"])
def test_invalid_limit_env_raises(monkeypatch, raw):
    monkeypatch.setenv("MAX_ATTACHMENT_MB", raw)

    with pytest.raises(RuntimeError, match="MAX_ATTACHMENT_MB"):
        AttachmentLimits.from_env()


def test_detects_type_from_bytes_not_the_name():
    assert detect_media_type("photo.jpg", PNG) == "image/png"
    assert detect_media_type("paper.txt", PDF) == "application/pdf"
    assert detect_media_type("notes.md", b"# Title\n") == "text/plain"


def test_rejects_unknown_and_binary_files():
    assert detect_media_type("tool.exe", b"MZ\x90\x00") is None
    assert detect_media_type("notes.txt", b"bad\x00bytes") is None
    assert detect_media_type("notes.txt", b"\xff\xfe not utf-8 \xc3") is None


def test_clean_filename_keeps_base_name_only():
    assert clean_filename("C:\\Users\\me\\report.pdf") == "report.pdf"
    assert clean_filename("../../etc/passwd") == "passwd"
    assert clean_filename('a"b<c>.txt') == "abc.txt"
    assert clean_filename("") == "file"


def test_prepares_valid_files():
    files = [UploadedFile("shot.png", PNG), UploadedFile("paper.pdf", PDF)]

    attachments = prepare_attachments(files, AttachmentLimits(), existing_bytes=0)

    assert [(a.filename, a.media_type, a.size) for a in attachments] == [
        ("shot.png", "image/png", len(PNG)),
        ("paper.pdf", "application/pdf", len(PDF)),
    ]


def test_rejects_too_many_files():
    limits = AttachmentLimits(max_files=2)
    files = [UploadedFile(f"{i}.png", PNG) for i in range(3)]

    with pytest.raises(ValueError, match="up to 2 files"):
        prepare_attachments(files, limits, existing_bytes=0)


def test_rejects_file_over_per_file_limit():
    limits = AttachmentLimits(max_file_bytes=MB)
    big = PNG + b"0" * MB

    with pytest.raises(ValueError, match="big.png is larger than 1 MB"):
        prepare_attachments([UploadedFile("big.png", big)], limits, existing_bytes=0)


def test_rejects_combined_size_over_message_limit():
    limits = AttachmentLimits(max_file_bytes=MB, max_total_bytes=MB)
    half = PNG + b"0" * (MB // 2 + 1)

    with pytest.raises(ValueError, match="total at most 1 MB"):
        prepare_attachments(
            [UploadedFile("a.png", half), UploadedFile("b.png", half)],
            limits,
            existing_bytes=0,
        )


def test_rejects_when_session_limit_would_be_exceeded():
    limits = AttachmentLimits(max_session_bytes=MB)

    with pytest.raises(ValueError, match="attachment limit"):
        prepare_attachments(
            [UploadedFile("a.png", PNG)],
            limits,
            existing_bytes=MB,
        )


def test_rejects_unsupported_and_empty_files():
    with pytest.raises(ValueError, match="not a supported file"):
        prepare_attachments([UploadedFile("tool.exe", b"MZ\x90")], AttachmentLimits(), 0)

    with pytest.raises(ValueError, match="is empty"):
        prepare_attachments([UploadedFile("empty.txt", b"")], AttachmentLimits(), 0)
