from core.chat_core.service import ChatService
from core.chat_core.store import SessionStore


def main() -> None:
    store = SessionStore()
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
                print(chunk, end="", flush=True)
            print()
        except RuntimeError as error:
            print(f"\nConfiguration error: {error}")
        except Exception as error:
            print(f"\nRequest failed: {error}")


if __name__ == "__main__":
    main()