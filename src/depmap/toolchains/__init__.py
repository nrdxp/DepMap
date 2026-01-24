"""DepMap toolchain plugins for dependency resolution."""

from .base import (
    TOOLCHAIN_REGISTRY,
    Dependency,
    ToolchainPlugin,
    register_toolchain,
)

# Import plugins to trigger auto-registration
from . import rust  # noqa: F401

__all__ = [
    "TOOLCHAIN_REGISTRY",
    "Dependency",
    "ToolchainPlugin",
    "register_toolchain",
]
