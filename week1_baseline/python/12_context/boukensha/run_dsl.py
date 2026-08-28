"""The boukensha.run() DSL surface.

Python port of Boukensha::RunDSL.
"""

from __future__ import annotations

from typing import Any, Callable


class RunDSL:
    """Passed to the `configure` callback given to `boukensha.run()`.

    Exposes exactly one method, `tool`, mirroring Ruby's `RunDSL` — the
    caller can register tools but cannot reach the `Context`, `Client`, or
    any other internal object.
    """

    def __init__(self, registry) -> None:
        self._registry = registry

    def tool(self, name, *, description: str, parameters: dict | None = None,
             block: Callable[..., Any]):
        return self._registry.tool(
            name, description=description, parameters=parameters or {}, block=block
        )
