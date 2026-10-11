import cli.main
from cli.main import SPINNER_FRAMES, ModelCompleter, Spinner, format_info
from core.chat_core.providers import ModelInfo, TextDelta
from core.chat_core.service import ChatService
from core.chat_core.settings import Settings
from core.chat_core.store import InMemorySessionStore


def test_info_line_shows_model_usage_and_time():
    reply = {
        "model": "claude-sonnet-5-5",
        "usage": {"inputTokens": 12, "outputTokens": 5, "costUsd": 0.00042},
        "durationMs": 1234,
    }

    assert format_info(reply) == (
        "Model: claude-sonnet-5-5 · 12 input · 5 output · $0.000420 · 1.2 s"
    )


def test_info_line_handles_missing_usage_and_model():
    reply = {"model": "", "usage": None, "durationMs": None}

    assert format_info(reply) == "Model: unknown"


def test_spinner_erases_itself_before_text_and_at_the_end(capsys):
    spinner = Spinner(enabled=True)

    spinner.start()
    spinner.write("Hi")
    spinner.stop()

    output = capsys.readouterr().out
    first_frame = SPINNER_FRAMES[0]
    assert output.startswith(first_frame)
    assert f"\b \b{'Hi'}" in output
    assert output.endswith("\b \b")


def test_spinner_writes_plain_text_when_disabled(capsys):
    spinner = Spinner(enabled=False)

    spinner.start()
    spinner.write("Hi")
    spinner.stop()

    assert capsys.readouterr().out == "Hi"


class FakeModelProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def stream(self, *, model, messages, tools):
        self.calls.append(model)
        yield TextDelta("ok")

    def list_models(self):
        return [ModelInfo(id="anthropic/alpha", name="Alpha"), ModelInfo(id="openai/beta", name="Beta")]


class FakeReadline:
    def __init__(self, line: str) -> None:
        self.line = line

    def get_line_buffer(self) -> str:
        return self.line


def test_completer_completes_model_ids_after_model_command(monkeypatch):
    monkeypatch.setattr(cli.main, "readline", FakeReadline("/model an"))
    completer = ModelCompleter(ChatService(InMemorySessionStore(), provider=FakeModelProvider(),
                                           settings=Settings(provider="openrouter", api_key="k", model="x")))

    assert completer("an", 0) == "anthropic/alpha"
    assert completer("an", 1) is None


def test_completer_completes_commands_before_a_space(monkeypatch):
    monkeypatch.setattr(cli.main, "readline", FakeReadline("/mo"))
    completer = ModelCompleter(ChatService(InMemorySessionStore(), provider=FakeModelProvider(),
                                           settings=Settings(provider="openrouter", api_key="k", model="x")))

    assert completer("/mo", 0) == "/model"
    assert completer("/mo", 1) is None


def test_model_command_switches_the_model_for_the_next_message(monkeypatch, capsys):
    provider = FakeModelProvider()
    store = InMemorySessionStore()
    service = ChatService(store, provider=provider,
                          settings=Settings(provider="openrouter", api_key="k", model="default/model"))
    inputs = iter(["/model", "/model openai/beta", "hi", "/quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    monkeypatch.setattr(cli.main, "setup_readline", lambda completer: None)

    cli.main.main(service)

    output = capsys.readouterr().out
    assert "Current model: default/model" in output
    assert "Model set to openai/beta" in output
    assert provider.calls == ["openai/beta"]


def test_model_command_rejects_unknown_model(monkeypatch, capsys):
    provider = FakeModelProvider()
    store = InMemorySessionStore()
    service = ChatService(store, provider=provider,
                          settings=Settings(provider="openrouter", api_key="k", model="default/model"))
    inputs = iter(["/model nope", "hi", "/quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    monkeypatch.setattr(cli.main, "setup_readline", lambda completer: None)

    cli.main.main(service)

    assert "Unknown model: nope" in capsys.readouterr().out
    assert provider.calls == ["default/model"]
