"""DepMap toolchain plugins for dependency resolution."""

# Import plugins to trigger auto-registration
from . import (
    go,  # noqa: F401
    rust,  # noqa: F401
)
from .base import (
    TOOLCHAIN_REGISTRY,
    Dependency,
    DepMapError,
    ResolutionError,
    ToolchainError,
    ToolchainPlugin,
    register_toolchain,
)

__all__ = [
    "TOOLCHAIN_REGISTRY",
    "DepMapError",
    "Dependency",
    "ResolutionError",
    "ToolchainError",
    "ToolchainPlugin",
    "register_toolchain",
]
