"""Base interfaces and registry for toolchain plugins."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class DepMapError(Exception):
    """Base exception for all DepMap errors."""

    pass


class ToolchainError(DepMapError):
    """Error during toolchain detection or dependency parsing."""

    def __init__(self, toolchain: str, message: str, cause: Exception | None = None):
        self.toolchain = toolchain
        self.cause = cause
        super().__init__(f"[{toolchain}] {message}")
        if cause:
            self.__cause__ = cause


class ResolutionError(DepMapError):
    """Error during dependency resolution."""

    def __init__(self, message: str, cause: Exception | None = None):
        self.cause = cause
        super().__init__(message)
        if cause:
            self.__cause__ = cause


@dataclass
class Dependency:
    """Represents a resolved dependency."""

    name: str
    version: str
    toolchain: str
    source_path: Path | None = None


class ToolchainPlugin(Protocol):
    """Protocol defining the interface for toolchain plugins."""

    name: str

    def detect(self, project_root: Path) -> bool:
        """Return True if this toolchain is detected in the project."""
        ...

    def list_dependencies(self, project_root: Path) -> list[Dependency]:
        """Parse manifest and return list of dependencies."""
        ...

    def locate_source(self, dep: Dependency) -> Path | None:
        """Find the local source location for a dependency."""
        ...


TOOLCHAIN_REGISTRY: dict[str, ToolchainPlugin] = {}


def register_toolchain(plugin: ToolchainPlugin) -> None:
    """Register a toolchain plugin in the global registry."""
    TOOLCHAIN_REGISTRY[plugin.name] = plugin

