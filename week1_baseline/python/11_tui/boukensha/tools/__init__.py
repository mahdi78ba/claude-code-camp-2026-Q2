"""Boukensha's standard tool library.

Python port of Boukensha::Tools. Three independent registration modules —
file_system, shell, mcp — each exposing a module-level register(registry, ...)
function. Ruby's Tools::FileSystem/.Shell/.Mcp are each a bare module
namespace holding one class method, not a stateful object, so a plain
function per file is the direct equivalent here, not a class with one
method.
"""

from . import file_system, shell, mcp

__all__ = ["file_system", "shell", "mcp"]
