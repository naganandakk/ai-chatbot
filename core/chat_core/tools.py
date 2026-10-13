from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolInfo:
    id: str
    name: str
    description: str

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description}


# Tools a user can switch on for a message. Every tool is off unless the user turns it on.
# Providers map these ids to their own tools and ignore the ones they do not support.
TOOLS: tuple[ToolInfo, ...] = (
    ToolInfo(
        id="web_search",
        name="Web search",
        description="Search the web for current information and cite its sources.",
    ),
)

_TOOL_IDS = {tool.id for tool in TOOLS}


def checked_tools(names: Sequence[str]) -> list[str]:
    # Repeats are dropped and the order the user picked is kept. An unknown name is refused
    # rather than ignored, so a bad request never silently changes what the model can do.
    for name in names:
        if not isinstance(name, str) or name not in _TOOL_IDS:
            raise ValueError(f"Unknown tool: {name}")

    return list(dict.fromkeys(names))
