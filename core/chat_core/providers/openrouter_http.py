import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import httpx


class CitationStream(httpx.SyncByteStream):
    def __init__(self, stream: httpx.SyncByteStream, sources: list[dict]) -> None:
        self.stream = stream
        self.sources = sources
        self.buffer = b""

    def __iter__(self) -> Iterator[bytes]:
        for chunk in self.stream:
            self.buffer += chunk
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                self._record(line)
            yield chunk

    def close(self) -> None:
        self.stream.close()

    def _record(self, line: bytes) -> None:
        if not line.startswith(b"data: ") or line == b"data: [DONE]":
            return

        try:
            data = json.loads(line[len(b"data: "):])
        except json.JSONDecodeError:
            return

        for choice in data.get("choices", []):
            for annotation in (choice.get("delta") or {}).get("annotations") or []:
                if annotation.get("type") != "url_citation":
                    continue

                citation = annotation["url_citation"]
                source = {"title": citation.get("title", ""), "url": citation.get("url", "")}
                if source not in self.sources:
                    self.sources.append(source)


class CitationHttpClient(httpx.Client):
    # The OpenRouter SDK drops `annotations` from streamed deltas because its
    # models do not define the field. This client reads url_citation sources
    # from the raw SSE lines while the SDK keeps parsing the stream. The sources
    # list is bound per thread with `collecting`, so concurrent requests on
    # threaded workers each record into their own list.
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        super().__init__(transport=transport)
        self._local = threading.local()

    @contextmanager
    def collecting(self, sources: list[dict]) -> Iterator[None]:
        self._local.sources = sources
        try:
            yield
        finally:
            self._local.sources = None

    def send(self, request: httpx.Request, *, stream: bool = False, **kwargs) -> httpx.Response:
        response = super().send(request, stream=stream, **kwargs)
        sources = getattr(self._local, "sources", None)

        if stream and sources is not None:
            response.stream = CitationStream(response.stream, sources)

        return response
