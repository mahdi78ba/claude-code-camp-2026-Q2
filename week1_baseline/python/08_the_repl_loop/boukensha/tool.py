"""A tool the agent can invoke.

Python port of Boukensha::Tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(repr=False)
class Tool:
    name: str
    description: str
    parameters: dict
    block: Callable[..., str]

    def __str__(self) -> str:
        params = ", ".join(f":{k}" for k in self.parameters.keys())
        return (
            f"#<Tool name={self.name} description={self.description[:41]} "
            f"params=[{params}]>"
        )

    __repr__ = __str__
