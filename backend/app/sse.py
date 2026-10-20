import json
from typing import Any


def format_event(name: str, data: Any) -> str:
    """One server-sent event frame. The frontend splits on the blank line that ends each frame."""
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"
