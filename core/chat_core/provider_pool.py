import hashlib
import threading
from collections import OrderedDict

from .providers import ModelProvider, create_provider_for
from .settings import DEFAULT_MAX_TOKENS


class ProviderPool:
    """Keeps one provider per (provider, API key) so each user's requests reuse a connection.

    Entries are keyed by a hash of the key, so the pool holds no plaintext key as a lookup
    value. The least recently used provider is closed once the pool is full. A user who
    replaces their key gets a new provider, and the old one ages out.
    """

    def __init__(self, max_size: int = 64) -> None:
        self._max_size = max_size
        self._providers: OrderedDict[tuple[str, str], ModelProvider] = OrderedDict()
        self._lock = threading.Lock()

    def get(
        self,
        provider_name: str,
        api_key: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ModelProvider:
        cache_key = (provider_name, hashlib.sha256(api_key.encode()).hexdigest())

        with self._lock:
            provider = self._providers.get(cache_key)

            if provider is not None:
                self._providers.move_to_end(cache_key)
                return provider

            provider = create_provider_for(provider_name, api_key, max_tokens)
            self._providers[cache_key] = provider

            while len(self._providers) > self._max_size:
                _, evicted = self._providers.popitem(last=False)
                evicted.close()

            return provider

    def close(self) -> None:
        with self._lock:
            while self._providers:
                _, provider = self._providers.popitem()
                provider.close()
