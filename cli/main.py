from core.chat_core.providers import ProviderError, ReplyReset
from core.chat_core.service import ChatService
from core.chat_core.store import InMemorySessionStore


def print_summary(message: dict) -> None:
    parts = []
    usage = message["usage"]
    if usage is not None:
        cost = "cost unavailable" if usage["costUsd"] is None else f"${usage['costUsd']:.6f}"
        parts.append(f"{usage['inputTokens']} input, {usage['outputTokens']} output, {cost}")
    if message["durationMs"] is not None:
        parts.append(f"{message['durationMs'] / 1000:.1f} s")

    if parts:
        print(f"[{', '.join(parts)}]")


def main() -> None:
    store = InMemorySessionStore()
    service = ChatService(store)
    session = store.create()

    print("AI Chat CLI")
    print("Commands: /new, /clear, /quit")

    while True:
        try:
            prompt = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if prompt == "/quit":
            return

        if prompt == "/new":
            session = store.create()
            print("Started a new chat.")
            continue

        if prompt == "/clear":
            store.clear(session.id)
            print("Chat history cleared.")
            continue

        if not prompt:
            continue

        print("Assistant: ", end="", flush=True)

        try:
            for chunk in service.stream_reply(session.id, prompt):
                # The CLI sends no tools, so it never gets a reset; text already printed can't be taken back
                if isinstance(chunk, ReplyReset):
                    continue
                print(chunk, end="", flush=True)
            print()
            print_summary(store.get(session.id).messages[-1].to_dict())
        except RuntimeError as error:
            print(f"\nConfiguration error: {error}")
        except ProviderError as error:
            print(f"\nRequest failed: {error}")


if __name__ == "__main__":
    main()