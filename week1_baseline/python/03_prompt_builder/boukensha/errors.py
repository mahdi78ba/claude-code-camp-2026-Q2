"""Boukensha-specific error classes.

Python port of Boukensha::UnknownToolError and Boukensha::UnsupportedModelError.
Flat, single-level custom exceptions — mirrors the Ruby reference's own
choice not to introduce a shared error base class yet.
"""

from __future__ import annotations


class UnknownToolError(Exception):
    """Raised when dispatch is called with a name that has no registered tool."""


class UnsupportedModelError(Exception):
    """Raised when a backend is initialized with a model it doesn't support."""
