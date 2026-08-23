"""Serializes a Context for the exact wire format a backend expects.

Python port of Boukensha::PromptBuilder. A pure delegator — no formatting
logic of its own, just a stable, provider-agnostic surface over whichever
backend it was constructed with.
"""

from __future__ import annotations


class PromptBuilder:
    def __init__(self, context, backend) -> None:
        self.context = context
        self.backend = backend

    def to_messages(self):
        return self.backend.to_messages(self.context.messages)

    def to_tools(self):
        return self.backend.to_tools(self.context.tools)

    def to_api_payload(self, *, max_output_tokens=1024, tools=None):
        return self.backend.to_payload(
            self.context, max_output_tokens=max_output_tokens, tools=tools
        )

    def parse_response(self, response):
        return self.backend.parse_response(response)

    @property
    def headers(self):
        return self.backend.headers

    @property
    def url(self):
        return self.backend.url
