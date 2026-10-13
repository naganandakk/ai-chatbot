import hashlib
import threading
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

# Below this size a cache write costs more than the reads it would save
MIN_CACHE_TOKENS = 2048
# A 5 minute entry expires before a user who pauses this long sends the next turn
SLOW_TURN_GAP = timedelta(minutes=4)
# Consecutive turns that wrote to the cache but read nothing before caching is paused
MISSES_BEFORE_PAUSE = 2
PAUSE_FOR = timedelta(minutes=30)
MAX_CONVERSATIONS = 256

CACHE_5M = {"type": "ephemeral"}
CACHE_1H = {"type": "ephemeral", "ttl": "1h"}


class _Conversation:
    def __init__(self) -> None:
        self.last_request_at: datetime | None = None
        self.turns = 0
        self.misses = 0
        self.paused_until: datetime | None = None


class CachePolicy:
    """Decides, per request, whether to send a top-level `cache_control` marker.

    One instance belongs to one provider, which is one user's key. Conversations are keyed by
    model and first message, so the key is the same on every turn without a session id.
    """

    def __init__(self, applies_to: Callable[[str], bool] = lambda model: True) -> None:
        self._applies_to = applies_to
        self._conversations: OrderedDict[str, _Conversation] = OrderedDict()
        self._lock = threading.Lock()

    def params_for(self, *, model: str, messages: list[dict]) -> dict:
        if not self._applies_to(model) or estimate_tokens(messages) < MIN_CACHE_TOKENS:
            return {}

        now = _now()
        key = conversation_key(model, messages)
        with self._lock:
            state = self._state(key)
            if state.paused_until and now < state.paused_until:
                return {}

            # The 5 minute entry from the last turn has expired by now, so write a 1 hour one
            slow = state.last_request_at is not None and now - state.last_request_at > SLOW_TURN_GAP
            state.last_request_at = now
            state.paused_until = None
            return {"cache_control": dict(CACHE_1H if slow else CACHE_5M)}

    def record(
        self,
        *,
        model: str,
        messages: list[dict],
        cache_write_tokens: int,
        cache_read_tokens: int,
    ) -> None:
        if not self._applies_to(model):
            return

        key = conversation_key(model, messages)
        with self._lock:
            state = self._state(key)
            state.turns += 1

            if cache_read_tokens > 0:
                state.misses = 0
            elif cache_write_tokens > 0 and state.turns > 1:
                # The first turn is expected to write with nothing to read yet
                state.misses += 1
                if state.misses >= MISSES_BEFORE_PAUSE:
                    state.paused_until = _now() + PAUSE_FOR
                    state.misses = 0

    def _state(self, key: str) -> _Conversation:
        state = self._conversations.get(key)
        if state is None:
            state = _Conversation()
            self._conversations[key] = state
            if len(self._conversations) > MAX_CONVERSATIONS:
                self._conversations.popitem(last=False)
        else:
            self._conversations.move_to_end(key)
        return state


def conversation_key(model: str, messages: list[dict]) -> str:
    first = messages[0]["content"] if messages else ""
    if not isinstance(first, str):
        first = "".join(block.get("text", "") for block in first if block.get("type") == "text")
    return hashlib.sha256(f"{model}\0{first}".encode()).hexdigest()


def estimate_tokens(messages: list[dict]) -> int:
    # Roughly four characters per token for text; attachment bytes are a coarse proxy
    total = 0
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            total += len(content) // 4
            continue
        for block in content:
            if block["type"] == "text":
                total += len(block["text"]) // 4
            else:
                total += len(block["data"]) // 3
    return total


def _now() -> datetime:
    return datetime.now(UTC)
