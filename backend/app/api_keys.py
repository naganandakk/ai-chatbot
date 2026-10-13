from flask import Flask, g, jsonify, request
from flask_limiter import Limiter

from core.chat_core.accounts import AccountStore
from core.chat_core.key_vault import KeyVault
from core.chat_core.providers import PROVIDERS, ProviderError, create_provider_for
from core.chat_core.service import ChatService


def register_api_key_routes(
    app: Flask,
    accounts: AccountStore,
    vault: KeyVault,
    service: ChatService,
    limiter: Limiter,
) -> None:
    # Keys are write-only: after saving, the API returns only whether one is set and its last
    # four characters. The full key is never sent back, logged, or put in an error message.

    def key_statuses() -> list[dict]:
        saved = {record.provider: record for record in accounts.list_api_keys(g.user_id)}

        return [
            {
                "provider": provider,
                "configured": provider in saved,
                "last4": saved[provider].last4 if provider in saved else None,
            }
            for provider in sorted(PROVIDERS)
        ]

    def settings_json() -> dict:
        return {
            "activeProvider": accounts.get_active_provider(g.user_id),
            "providers": key_statuses(),
        }

    @app.get("/api/me/api-keys")
    def list_api_keys():
        return jsonify(key_statuses())

    @app.put("/api/me/api-keys/<provider>")
    @limiter.limit("5 per minute")
    def save_api_key(provider: str):
        if provider not in PROVIDERS:
            return jsonify({"error": "Unknown provider"}), 404

        api_key = ((request.get_json(silent=True) or {}).get("apiKey") or "").strip()

        if not api_key:
            return jsonify({"error": "Enter an API key", "code": "api_key_missing"}), 400

        # A cheap call with the key proves it works before anything is stored
        candidate = create_provider_for(provider, api_key, service.max_tokens)
        try:
            candidate.list_models()
        except ProviderError:
            return jsonify({
                "error": f"{provider} did not accept this API key",
                "code": "api_key_invalid",
            }), 422
        finally:
            candidate.close()

        last4 = api_key[-4:]
        accounts.save_api_key(g.user_id, provider, vault.encrypt(g.user_id, provider, api_key), last4)
        accounts.record_audit_event(g.user_id, "api_key.saved", provider)

        # The first key saved becomes the provider in use, so a new user can chat straight away
        if accounts.get_active_provider(g.user_id) is None:
            accounts.set_active_provider(g.user_id, provider)

        return jsonify({"provider": provider, "configured": True, "last4": last4})

    @app.delete("/api/me/api-keys/<provider>")
    def delete_api_key(provider: str):
        if provider not in PROVIDERS:
            return jsonify({"error": "Unknown provider"}), 404

        accounts.delete_api_key(g.user_id, provider)
        accounts.record_audit_event(g.user_id, "api_key.deleted", provider)

        # A provider without a key cannot be in use, so the choice is cleared
        if accounts.get_active_provider(g.user_id) == provider:
            accounts.set_active_provider(g.user_id, None)

        return jsonify({"provider": provider, "configured": False, "last4": None})

    @app.get("/api/me/settings")
    def get_settings():
        return jsonify(settings_json())

    @app.put("/api/me/settings")
    def update_settings():
        provider = (request.get_json(silent=True) or {}).get("activeProvider")

        if provider is not None:
            provider = str(provider).strip().lower()

            if provider not in PROVIDERS:
                return jsonify({"error": "Unknown provider"}), 400

            if accounts.get_api_key(g.user_id, provider) is None:
                return jsonify({
                    "error": f"Add an API key for {provider} before using it",
                    "code": "api_key_required",
                }), 409

        accounts.set_active_provider(g.user_id, provider)
        return jsonify(settings_json())
