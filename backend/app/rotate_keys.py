"""Re-seal saved provider API keys under the current KEY_ENCRYPTION_KEYS entry.

Prepend the new key to KEY_ENCRYPTION_KEYS, keep the old one after it, then run:

    uv run python -m backend.app.rotate_keys --dry-run
    uv run python -m backend.app.rotate_keys

With CHAT_STORE=duckdb, stop the app first: DuckDB allows one writer at a time.
Plaintext keys are only held in memory and are never printed.
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from core.chat_core.key_vault import KeyVault, KeyVaultError
from core.chat_core.stores import create_store

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="count the rows that would move without changing anything",
    )
    args = parser.parse_args(argv)

    key_vault = KeyVault.from_env()
    store = create_store()
    counts = {"moved": 0, "current": 0, "changed": 0, "failed": 0}

    try:
        for user_id, record in store.list_all_api_keys():
            label = f"{user_id} {record.provider}"

            if record.sealed.key_version == key_vault.current_version:
                counts["current"] += 1
                continue

            try:
                resealed = key_vault.reseal(user_id, record.provider, record.sealed)
            except KeyVaultError:
                counts["failed"] += 1
                print(f"FAILED   {label}: sealed by a key that is no longer configured")
                continue

            if args.dry_run:
                counts["moved"] += 1
                print(f"WOULD MOVE {label}")
                continue

            # The compare-and-swap fails only if the user saved or deleted the key while this ran.
            # A re-saved key is already sealed under the current key, so leave it alone.
            if store.replace_api_key_seal(user_id, record.provider, record.sealed, resealed):
                store.record_audit_event(user_id, "rekey", record.provider)
                counts["moved"] += 1
                print(f"MOVED    {label}")
            else:
                counts["changed"] += 1
                print(f"CHANGED  {label}: saved or deleted during the run, left as is")
    finally:
        store.close()

    print(
        f"moved={counts['moved']} already_current={counts['current']} "
        f"changed_during_run={counts['changed']} failed={counts['failed']}"
        + (" (dry run)" if args.dry_run else "")
    )
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
