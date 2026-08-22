"""Boukensha-specific error classes.

Python port of Boukensha::UnknownToolError. Flat, single custom exception —
mirrors the Ruby reference's own choice not to introduce a shared error
base class yet.
"""

from __future__ import annotations


class UnknownToolError(Exception):
    """Raised when dispatch is called with a name that has no registered tool."""
