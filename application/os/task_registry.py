from __future__ import annotations

from typing import Any, Callable


class TaskRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

    def register(self, name: str, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self._handlers[name] = handler

    def get(self, name: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
        if name not in self._handlers:
            raise KeyError(f"Task pipeline '{name}' not found in registry")
        return self._handlers[name]
