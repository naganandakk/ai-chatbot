from core.chat_core.provider_pool import ProviderPool


class ClosableProvider:
    def __init__(self, provider_name: str, api_key: str, max_tokens: int = 0) -> None:
        self.provider_name = provider_name
        self.api_key = api_key
        self.closed = False

    def close(self) -> None:
        self.closed = True


def patch_factory(monkeypatch):
    created: list[ClosableProvider] = []

    def fake_create(provider_name, api_key, max_tokens=0):
        provider = ClosableProvider(provider_name, api_key, max_tokens)
        created.append(provider)
        return provider

    monkeypatch.setattr("core.chat_core.provider_pool.create_provider_for", fake_create)
    return created


def test_same_provider_and_key_reuse_one_instance(monkeypatch):
    created = patch_factory(monkeypatch)
    pool = ProviderPool()

    first = pool.get("anthropic", "sk-ant-one")
    second = pool.get("anthropic", "sk-ant-one")

    assert first is second
    assert len(created) == 1


def test_different_keys_or_providers_get_different_instances(monkeypatch):
    patch_factory(monkeypatch)
    pool = ProviderPool()

    assert pool.get("anthropic", "sk-ant-one") is not pool.get("anthropic", "sk-ant-two")
    assert pool.get("anthropic", "same") is not pool.get("openrouter", "same")


def test_least_recently_used_provider_is_closed_when_the_pool_is_full(monkeypatch):
    created = patch_factory(monkeypatch)
    pool = ProviderPool(max_size=2)

    oldest = pool.get("anthropic", "key-1")
    pool.get("anthropic", "key-2")
    pool.get("anthropic", "key-1")  # touching key-1 makes key-2 the least recently used
    pool.get("anthropic", "key-3")

    assert [provider.closed for provider in created] == [False, True, False]
    assert pool.get("anthropic", "key-1") is oldest


def test_close_releases_every_provider(monkeypatch):
    created = patch_factory(monkeypatch)
    pool = ProviderPool()
    pool.get("anthropic", "key-1")
    pool.get("openrouter", "key-2")

    pool.close()

    assert all(provider.closed for provider in created)
