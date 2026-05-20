"""Python toolchain plugin for DepMap."""

import re
import tomllib
from pathlib import Path

from .base import Dependency, ToolchainError, register_toolchain


class PythonToolchain:
    """Python toolchain plugin."""

    name = "python"

    def __init__(self):
        self.project_root: Path | None = None

    def detect(self, project_root: Path) -> bool:
        """Return True if Python dependency manifests exist in project root."""
        self.project_root = project_root
        return (
            (project_root / "requirements.txt").exists()
            or (project_root / "pyproject.toml").exists()
            or (project_root / "poetry.lock").exists()
            or (project_root / "Pipfile").exists()
        )

    def list_dependencies(self, project_root: Path) -> list[Dependency]:
        """Parse requirements.txt and/or pyproject.toml to extract dependencies.

        Gathers package names and versions.
        Attempts to read exact installed versions and paths from local site-packages.
        Returns empty list for missing manifests.
        Raises ToolchainError for I/O errors.
        """
        self.project_root = project_root
        raw_deps: dict[str, str] = {}

        # 1. Parse pyproject.toml if present
        pyproject_path = project_root / "pyproject.toml"
        if pyproject_path.exists():
            try:
                with open(pyproject_path, "rb") as f:
                    content = f.read()
                    data = tomllib.loads(content.decode("utf-8")) if content.strip() else {}
            except tomllib.TOMLDecodeError:
                # Malformed TOML - degrade gracefully to keep parsing other files
                data = {}
            except OSError as e:
                raise ToolchainError(self.name, f"Failed to read pyproject.toml: {e}", e) from e

            if isinstance(data, dict):
                # Standard PEP 621 dependencies
                pep621_deps = data.get("project", {}).get("dependencies", [])
                if isinstance(pep621_deps, list):
                    for dep_str in pep621_deps:
                        if isinstance(dep_str, str):
                            name, ver = self._parse_pep508_string(dep_str)
                            if name:
                                raw_deps[name] = ver

                # Poetry dependencies
                poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
                if isinstance(poetry_deps, dict):
                    for name, val in poetry_deps.items():
                        if not isinstance(name, str) or name.lower() == "python":
                            continue
                        version = "unknown"
                        if isinstance(val, str):
                            version = val
                        elif isinstance(val, dict) and "version" in val:
                            version = val["version"]
                        raw_deps[name] = version

        # 2. Parse requirements.txt if present
        reqs_path = project_root / "requirements.txt"
        if reqs_path.exists():
            try:
                with open(reqs_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or line.startswith("-"):
                            continue
                        if " #" in line:
                            line = line.split(" #")[0].strip()
                        name, ver = self._parse_pep508_string(line)
                        if name:
                            raw_deps[name] = ver
            except OSError as e:
                raise ToolchainError(self.name, f"Failed to read requirements.txt: {e}", e) from e

        deps = []
        for dep_name, version_spec in raw_deps.items():
            # Resolve exact installed version and path using our helper
            installed_version, _ = self._find_package_info(dep_name)
            version = installed_version if installed_version != "unknown" else version_spec

            deps.append(
                Dependency(
                    name=dep_name,
                    version=version,
                    toolchain=self.name,
                    source_path=None,  # Resolved later by locate_source
                )
            )

        return deps

    def locate_source(self, dep: Dependency) -> Path | None:
        """Find local source directory for a Python dependency.

        Searches in project virtual environments, active env, and user-site packages.
        """
        _, source_path = self._find_package_info(dep.name)
        return source_path

    def _parse_pep508_string(self, dep_str: str) -> tuple[str | None, str]:
        """Parse a PEP 508 dependency string into (package_name, version_specifier)."""
        dep_str = dep_str.strip()
        # Regex to match leading package name (alphanumeric, dashes, underscores, dots)
        match = re.match(r"^([a-zA-Z0-9_\-\.]+)", dep_str)
        if not match:
            return None, "unknown"
        name = match.group(1)

        # Look for explicit version specifiers like == or >=
        version = "unknown"
        version_match = re.search(r"==\s*([a-zA-Z0-9_\-\.\+]+)", dep_str)
        if version_match:
            version = version_match.group(1)
        else:
            version_match = re.search(r">=\s*([a-zA-Z0-9_\-\.\+]+)", dep_str)
            if version_match:
                version = version_match.group(1)

        return name, version

    def _find_site_packages_dirs(self) -> list[Path]:
        """Find all site-packages directories in local venv, active env, and user-site."""
        dirs = []

        # 1. Project-local virtual environments
        if self.project_root:
            for venv_name in (".venv", "venv"):
                venv_path = self.project_root / venv_name
                if venv_path.exists() and venv_path.is_dir():
                    # glob lib/python*/site-packages
                    for p in venv_path.glob("lib/python*/site-packages"):
                        if p.is_dir():
                            dirs.append(p.resolve())

        # 2. Active Python environment site-packages
        try:
            import site

            # getsitepackages can fail or return empty on some setups, wrap in try/except
            active_dirs = site.getsitepackages()
            for d in active_dirs:
                p = Path(d).resolve()
                if p.is_dir() and p not in dirs:
                    dirs.append(p)
        except Exception:
            pass

        # 3. User-site packages
        try:
            import site

            user_site = site.getusersitepackages()
            if user_site:
                p = Path(user_site).resolve()
                if p.is_dir() and p not in dirs:
                    dirs.append(p)
        except Exception:
            pass

        return dirs

    def _find_package_info(self, dep_name: str) -> tuple[str, Path | None]:
        """Find the version and source path for a dependency across all search dirs.

        Returns (installed_version, source_path).
        """
        search_dirs = self._find_site_packages_dirs()
        norm_name = dep_name.lower().replace("-", "_")

        for site_packages in search_dirs:
            # First pass: look for .dist-info or .egg-info directories to get exact metadata
            try:
                for p in site_packages.iterdir():
                    if p.is_dir() and (
                        p.name.endswith(".dist-info") or p.name.endswith(".egg-info")
                    ):
                        clean_name = p.name
                        if clean_name.endswith(".dist-info"):
                            clean_name = clean_name[:-10]
                        elif clean_name.endswith(".egg-info"):
                            clean_name = clean_name[:-9]

                        parts = clean_name.rsplit("-", 1)
                        if not parts:
                            continue
                        name_part = parts[0].lower().replace("-", "_")
                        if name_part == norm_name:
                            # Found metadata! Get version
                            version = "unknown"
                            if len(parts) > 1:
                                version = parts[1]

                            # Try to find code directory using top_level.txt if present
                            top_level_file = p / "top_level.txt"
                            if top_level_file.exists():
                                try:
                                    top_levels = top_level_file.read_text(
                                        encoding="utf-8"
                                    ).splitlines()
                                    for tl in top_levels:
                                        tl = tl.strip()
                                        if tl:
                                            code_dir = site_packages / tl
                                            if code_dir.exists():
                                                return version, code_dir
                                except Exception:
                                    pass

                            # Check direct module directory
                            code_dir = site_packages / norm_name
                            if code_dir.exists():
                                return version, code_dir

                            # Fallback to case-insensitive match for directory/file
                            for child in site_packages.iterdir():
                                if child.name.lower().replace("-", "_") == norm_name:
                                    return version, child
            except OSError:
                continue

            # Second pass: if no metadata directory matches, try finding the code directory/file directly
            try:
                for child in site_packages.iterdir():
                    child_norm = child.name.lower().replace("-", "_")
                    if child_norm == norm_name:
                        return "unknown", child
            except OSError:
                continue

        return "unknown", None


# Auto-register on import
register_toolchain(PythonToolchain())
