import sys
import threading

from core.chat_core.providers import ProviderError, ReplyReset
from core.chat_core.service import ChatService
from core.chat_core.store import InMemorySessionStore

try:
    import readline
except ImportError:  # Readline is missing on some platforms, so /model has no tab completion there
    readline = None

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
GRAY = "\033[90m"
RESET = "\033[0m"
COMMANDS = ["/clear", "/model", "/new", "/quit"]


class ModelCompleter:
    """Tab completes commands, and model IDs after /model.

    The model list is fetched from the provider the first time it is needed. A failed
    fetch completes nothing and is tried again on the next tab.
    """

    def __init__(self, service: ChatService) -> None:
        self._service = service
        self._model_ids: list[str] | None = None

    def set_model_ids(self, model_ids: list[str]) -> None:
        self._model_ids = model_ids

    def __call__(self, text: str, state: int) -> str | None:
        line = readline.get_line_buffer()
        if line.startswith("/model "):
            options = [model_id for model_id in self._load() if model_id.startswith(text)]
        elif line.startswith("/") and " " not in line:
            options = [command for command in COMMANDS if command.startswith(text)]
        else:
            options = []

        return options[state] if state < len(options) else None

    def _load(self) -> list[str]:
        if self._model_ids is None:
            try:
                self._model_ids = [model.id for model in self._service.list_models()]
            except (RuntimeError, ProviderError):
                return []

        return self._model_ids


def setup_readline(completer: ModelCompleter) -> None:
    if readline is None:
        return

    # Slashes are part of model IDs, so they must not split the word being completed
    readline.set_completer_delims(" \t\n")
    readline.set_completer(completer)
    # macOS Python uses libedit, which needs a different binding for tab
    if "libedit" in (readline.__doc__ or ""):
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")


class Spinner:
    """Shows a spinner after the reply text while it streams.

    The spinner is one character at the cursor. Each frame overwrites the last with a
    backspace, and text is written after erasing it, so the reply keeps its position.
    Nothing is drawn when stdout is not a terminal.
    """

    def __init__(self, enabled: bool) -> None:
        self._enabled = enabled
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._frame = 0
        self._active = False
        self._showing = False
        self._thread = threading.Thread(target=self._animate, daemon=True)

    def start(self) -> None:
        if not self._enabled:
            return

        with self._lock:
            self._active = True
            self._draw(SPINNER_FRAMES[0])
        self._thread.start()

    def write(self, text: str) -> None:
        with self._lock:
            self._erase()
            sys.stdout.write(text)
            if self._active:
                self._draw(SPINNER_FRAMES[self._frame])
            sys.stdout.flush()

    def stop(self) -> None:
        if not self._enabled or not self._thread.is_alive():
            return

        self._stop.set()
        self._thread.join()
        with self._lock:
            self._active = False
            self._erase()
            sys.stdout.flush()

    def _animate(self) -> None:
        while not self._stop.wait(0.1):
            with self._lock:
                self._frame = (self._frame + 1) % len(SPINNER_FRAMES)
                if self._active:
                    self._erase()
                    self._draw(SPINNER_FRAMES[self._frame])
                    sys.stdout.flush()

    def _draw(self, frame: str) -> None:
        sys.stdout.write(frame)
        self._showing = True

    def _erase(self) -> None:
        if self._showing:
            sys.stdout.write("\b \b")
            self._showing = False


def format_info(reply: dict) -> str:
    parts = [f"Model: {reply['model'] or 'unknown'}"]
    usage = reply["usage"]
    if usage is not None:
        cost = "cost unavailable" if usage["costUsd"] is None else f"${usage['costUsd']:.6f}"
        parts.append(f"{usage['inputTokens']} input")
        parts.append(f"{usage['outputTokens']} output")
        parts.append(cost)
    if reply["durationMs"] is not None:
        parts.append(f"{reply['durationMs'] / 1000:.1f} s")

    return " · ".join(parts)


def main(service: ChatService | None = None) -> None:
    store = service.store if service else InMemorySessionStore()
    service = service or ChatService(store)
    session = store.create()
    use_color = sys.stdout.isatty()
    # None uses the configured default model
    model: str | None = None
    completer = ModelCompleter(service)
    setup_readline(completer)

    print("AI Chat CLI")
    print("Commands: /new, /clear, /model, /quit")

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

        if prompt == "/model" or prompt.startswith("/model "):
            try:
                models = service.list_models()
            except (RuntimeError, ProviderError) as error:
                print(f"Could not load models: {error}")
                continue

            completer.set_model_ids([model_info.id for model_info in models])
            argument = prompt[len("/model"):].strip()

            if not argument:
                print(f"Current model: {model or service.default_model()}")
                for model_info in models:
                    print(f"  {model_info.id}  ({model_info.name})")
                print("Use /model <id> to switch. Tab completes model IDs.")
            elif argument not in {model_info.id for model_info in models}:
                print(f"Unknown model: {argument}. Type /model to list the models.")
            else:
                model = argument
                print(f"Model set to {model}. It is used for the next message.")
            continue

        if not prompt:
            continue

        print("Assistant: ", end="", flush=True)
        spinner = Spinner(enabled=use_color)

        try:
            spinner.start()
            try:
                for chunk in service.stream_reply(session.id, prompt, model):
                    # The CLI sends no tools, so it never gets a reset; text already printed can't be taken back
                    if isinstance(chunk, ReplyReset):
                        continue
                    spinner.write(chunk)
            finally:
                spinner.stop()

            reply = store.get(session.id).messages[-1].to_dict()
            # One blank line separates the reply from its info, which is dimmed when colors are on
            print("\n")
            info = format_info(reply)
            print(f"{GRAY}{info}{RESET}" if use_color else info)
        except RuntimeError as error:
            print(f"\nConfiguration error: {error}")
        except ProviderError as error:
            print(f"\nRequest failed: {error}")


if __name__ == "__main__":
    main()
