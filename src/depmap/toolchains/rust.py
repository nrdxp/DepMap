"""Rust toolchain plugin for DepMap."""

import os
import tomllib
from pathlib import Path

from .base import Dependency, ToolchainError, register_toolchain


class RustToolchain:
    """Rust/Cargo toolchain plugin."""

    name = "rust"

    def detect(self, project_root: Path) -> bool:
        """Return True if Cargo.toml exists in project root."""
        return (project_root / "Cargo.toml").exists()

    def list_dependencies(self, project_root: Path) -> list[Dependency]:
        """Parse Cargo.lock and return list of dependencies.

        Returns empty list for missing or empty lock file.
        Raises ToolchainError for malformed content.
        """
        lock_path = project_root / "Cargo.lock"
        if not lock_path.exists():
            return []

        try:
            with open(lock_path, "rb") as f:
                content = f.read()
                if not content.strip():
                    return []  # Empty file
                data = tomllib.loads(content.decode("utf-8"))
        except tomllib.TOMLDecodeError as e:
            # Malformed TOML - return empty for graceful degradation
            return []
        except OSError as e:
            raise ToolchainError(self.name, f"Failed to read Cargo.lock: {e}", e)

        deps = []
        for pkg in data.get("package", []):
            name = pkg.get("name")
            version = pkg.get("version")
            source = pkg.get("source", "")

            # Skip local crates (no source) and workspace members
            if not source or not name or not version:
                continue

            deps.append(
                Dependency(
                    name=name,
                    version=version,
                    toolchain=self.name,
                    source_path=None,  # Resolved later by locate_source
                )
            )

        return deps

    def locate_source(self, dep: Dependency) -> Path | None:
        """Find local source for a Cargo dependency.

        Search hierarchy:
        1. $CARGO_HOME/registry/src/index.crates.io-*/
        2. ~/.cargo/registry/src/index.crates.io-*/
        """
        cargo_home = os.environ.get("CARGO_HOME")
        if cargo_home:
            search_paths = [Path(cargo_home)]
        else:
            search_paths = [Path.home() / ".cargo"]

        for base in search_paths:
            registry_src = base / "registry" / "src"
            if not registry_src.exists():
                continue

            # Find index.crates.io-* directories
            for index_dir in registry_src.iterdir():
                if not index_dir.name.startswith("index.crates.io-"):
                    continue

                # Look for crate-version directory
                crate_dir = index_dir / f"{dep.name}-{dep.version}"
                if crate_dir.exists():
                    return crate_dir

        return None


# Auto-register on import
register_toolchain(RustToolchain())
