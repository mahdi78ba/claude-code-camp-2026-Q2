"""Shared backend contract for model validation and model metadata.

Python port of Boukensha::Backends::Base. Concrete backends define a
MODELS class attribute (str -> dict) and call self._configure_model(model)
from their own __init__ before doing anything else, so an unsupported
model raises UnsupportedModelError at construction time, not later.
"""

from __future__ import annotations

from ..errors import UnsupportedModelError


class Base:
    MODELS: dict = {}

    @classmethod
    def model_info_for(cls, model):
        return cls.MODELS.get(str(model))

    @classmethod
    def validate_model(cls, model):
        model = str(model)
        info = cls.model_info_for(model)
        if info is not None:
            return model
        supported = ", ".join(sorted(cls.MODELS.keys()))
        raise UnsupportedModelError(
            f"{cls.__name__} does not support model {model!r}. "
            f"Supported models: {supported}"
        )

    def __init__(self) -> None:
        self.model = None
        self.model_info = None

    def _configure_model(self, model) -> None:
        self.model = self.validate_model(model)
        self.model_info = self.model_info_for(self.model)

    @property
    def context_window(self):
        return self.model_info["context_window"]

    @property
    def input_token_cost_per_million(self):
        return self.model_info["cost_per_million"]["input"]

    @property
    def output_token_cost_per_million(self):
        return self.model_info["cost_per_million"]["output"]

    @property
    def usage_unit(self):
        return self.model_info["usage_unit"]

    @property
    def usage_level(self):
        return self.model_info.get("usage_level")

    def estimate_cost(self, *, input_tokens, output_tokens):
        input_cost = self.input_token_cost_per_million
        output_cost = self.output_token_cost_per_million
        if input_cost is None or output_cost is None:
            return None
        return (input_tokens * input_cost + output_tokens * output_cost) / 1_000_000.0
