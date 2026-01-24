"""Dependency resolution logic for DepMap."""

import logging
from dataclasses import asdict
from pathlib import Path

from .toolchains import TOOLCHAIN_REGISTRY, Dependency, ResolutionError, ToolchainError

log = logging.getLogger(__name__)


def resolve_project_dependencies(
    project_root: Path,
    toolchains: list[str] | None = None,
    deps: list[str] | None = None,
) -> dict:
    """Resolve dependencies for a project.

    Args:
        project_root: Root directory of the project
        toolchains: Optional list of toolchains to check (default: all registered)
        deps: Optional list of dependency names to filter by

    Returns:
        Dictionary with:
        - toolchains_detected: list of toolchain names found
        - dependencies: list of resolved dependency dicts
        - unresolved: list of dependency names that couldn't be located
    """
    detected_toolchains: list[str] = []
    all_deps: list[Dependency] = []
    unresolved: list[str] = []

    # Determine which toolchains to check
    if toolchains:
        plugins_to_check = [
            (name, TOOLCHAIN_REGISTRY[name])
            for name in toolchains
            if name in TOOLCHAIN_REGISTRY
        ]
    else:
        plugins_to_check = list(TOOLCHAIN_REGISTRY.items())

    # Detect toolchains and gather dependencies
    for name, plugin in plugins_to_check:
        try:
            if plugin.detect(project_root):
                detected_toolchains.append(name)
                plugin_deps = plugin.list_dependencies(project_root)
                all_deps.extend(plugin_deps)
        except Exception as e:
            log.warning(f"Error detecting toolchain {name}: {e}")

    # Filter by specific deps if requested
    if deps:
        dep_names_lower = {d.lower() for d in deps}
        all_deps = [d for d in all_deps if d.name.lower() in dep_names_lower]

    # Resolve source paths
    resolved_deps: list[dict] = []
    for dep in all_deps:
        plugin = TOOLCHAIN_REGISTRY.get(dep.toolchain)
        if plugin:
            try:
                source_path = plugin.locate_source(dep)
                dep.source_path = source_path
                if source_path is None:
                    unresolved.append(dep.name)
            except Exception as e:
                log.warning(f"Error locating {dep.name}: {e}")
                unresolved.append(dep.name)

        # Convert to dict for JSON serialization
        dep_dict = asdict(dep)
        if dep_dict["source_path"]:
            dep_dict["source_path"] = str(dep_dict["source_path"])
        resolved_deps.append(dep_dict)

    return {
        "toolchains_detected": detected_toolchains,
        "dependencies": resolved_deps,
        "unresolved": list(set(unresolved)),  # Deduplicate
    }
