"""DepMap toolchain plugins for dependency resolution."""

from .base import (
    TOOLCHAIN_REGISTRY,
    DepMapError,
    Dependency,
    ResolutionError,
    ToolchainError,
    ToolchainPlugin,
    register_toolchain,
)

# Import plugins to trigger auto-registration
from . import go  # noqa: F401
from . import rust  # noqa: F401

__all__ = [
    "TOOLCHAIN_REGISTRY",
    "DepMapError",
    "Dependency",
    "ResolutionError",
    "ToolchainError",
    "ToolchainPlugin",
    "register_toolchain",
]
