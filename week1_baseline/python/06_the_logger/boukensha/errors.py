"""Boukensha-specific error classes.

Python port of Boukensha::UnknownToolError, Boukensha::UnsupportedModelError,
and Boukensha::ApiError.
Flat, single-level custom exceptions — mirrors the Ruby reference's own
choice not to introduce a shared error base class yet.
"""

from __future__ import annotations


class UnknownToolError(Exception):
    """Raised when dispatch is called with a name that has no registered tool."""


class UnsupportedModelError(Exception):
    """Raised when a backend is initialized with a model it doesn't support."""


class ApiError(Exception):
    """Raised when an HTTP request to a provider's API fails."""
