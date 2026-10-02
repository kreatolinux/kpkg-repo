#!/usr/bin/env python3
"""Turn kpkg dependency-topology JSON into ordered GitHub Actions matrices."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MATRIX_LIMIT = 256
DEFAULT_MAX_LEVELS = 32


class TopologyError(ValueError):
    """The input topology cannot be planned safely."""


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise TopologyError(f"{field} must be an array")
    return value


def validate_document(document: Any) -> tuple[list[str], list[tuple[str, str]], list[str]]:
    """Validate schema v1 and return (nodes, edges, roots)."""
    if not isinstance(document, dict):
        raise TopologyError("topology must be a JSON object")
    schema_version = document.get("schema_version")
    if type(schema_version) is not int or schema_version != SCHEMA_VERSION:
        raise TopologyError("schema_version must be the integer 1")
    for field in ("roots", "nodes", "edges"):
        if field not in document:
            raise TopologyError(f"missing required field: {field}")

    names: list[str] = []
    for index, node in enumerate(_array(document["nodes"], "nodes")):
        if not isinstance(node, dict):
            raise TopologyError(f"nodes[{index}] must be an object")
        name = node.get("name")
        if not isinstance(name, str) or not name:
            raise TopologyError(f"nodes[{index}].name must be a non-empty string")
        names.append(name)
    if len(set(names)) != len(names):
        raise TopologyError("node names must be unique")
    node_set = set(names)

    roots = _array(document["roots"], "roots")
    if any(not isinstance(root, str) or not root for root in roots):
        raise TopologyError("roots must contain non-empty strings")
    if len(set(roots)) != len(roots):
        raise TopologyError("roots must be unique")
    unknown_roots = sorted(set(roots) - node_set)
    if unknown_roots:
        raise TopologyError(f"roots reference unknown nodes: {', '.join(unknown_roots)}")

    edges: list[tuple[str, str]] = []
    for index, edge in enumerate(_array(document["edges"], "edges")):
        if not isinstance(edge, dict):
            raise TopologyError(f"edges[{index}] must be an object")
        dependency = edge.get("dependency")
        dependent = edge.get("dependent")
        if not isinstance(dependency, str) or not dependency:
            raise TopologyError(f"edges[{index}].dependency must be a non-empty string")
        if not isinstance(dependent, str) or not dependent:
            raise TopologyError(f"edges[{index}].dependent must be a non-empty string")
        missing = sorted({dependency, dependent} - node_set)
        if missing:
            raise TopologyError(
                f"edges[{index}] references unknown nodes: {', '.join(missing)}"
            )
        edges.append((dependency, dependent))
    if len(set(edges)) != len(edges):
        raise TopologyError("edges must be unique")
    return sorted(names), sorted(edges), sorted(roots)


def strongly_connected_components(
    nodes: list[str], edges: list[tuple[str, str]]
) -> list[tuple[str, ...]]:
    """Return deterministic SCCs using Tarjan's algorithm."""
    adjacency = {node: [] for node in nodes}
    for source, target in edges:
        adjacency[source].append(target)
    for targets in adjacency.values():
        targets.sort()

    # Package repositories can contain more nodes than Python's default depth.
    sys.setrecursionlimit(max(sys.getrecursionlimit(), len(nodes) * 2 + 100))
    next_index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal next_index
        indices[node] = lowlinks[node] = next_index
        next_index += 1
        stack.append(node)
        on_stack.add(node)
        for target in adjacency[node]:
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])
        if lowlinks[node] == indices[node]:
            members: list[str] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                members.append(member)
                if member == node:
                    break
            components.append(tuple(sorted(members)))

    for node in sorted(nodes):
        if node not in indices:
            visit(node)
    return sorted(components)


def condensation_levels(
    nodes: list[str], edges: list[tuple[str, str]]
) -> list[list[tuple[str, ...]]]:
    """Condense cycles and form dependency-before-dependent Kahn levels."""
    components = strongly_connected_components(nodes, edges)
    component_for = {
        member: index for index, component in enumerate(components) for member in component
    }
    outgoing = {index: set() for index in range(len(components))}
    indegree = [0] * len(components)
    for dependency, dependent in edges:
        source = component_for[dependency]
        target = component_for[dependent]
        if source != target and target not in outgoing[source]:
            outgoing[source].add(target)
            indegree[target] += 1

    ready = sorted(index for index, degree in enumerate(indegree) if degree == 0)
    levels: list[list[tuple[str, ...]]] = []
    seen = 0
    while ready:
        levels.append(sorted((components[index] for index in ready)))
        seen += len(ready)
        following: list[int] = []
        for source in ready:
            for target in sorted(outgoing[source], key=lambda i: components[i]):
                indegree[target] -= 1
                if indegree[target] == 0:
                    following.append(target)
        ready = sorted(following, key=lambda i: components[i])
    if seen != len(components):  # Defensive: condensation graphs are acyclic.
        raise TopologyError("internal error: condensed graph contains a cycle")
    return levels


def _entries(components: list[tuple[str, ...]], arch: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for component in components:
        packages = " ".join(component)
        if arch in ("x86_64", "both"):
            entries.append({"packages": packages})
        if arch in ("arm64", "both"):
            entries.append({"packages": packages, "arch": "arm64"})
    if len(entries) > MATRIX_LIMIT:
        raise TopologyError(
            f"matrix has {len(entries)} entries; GitHub limit is {MATRIX_LIMIT}"
        )
    return entries


def plan_document(document: Any, arch: str = "both", max_levels: int = DEFAULT_MAX_LEVELS) -> dict[str, Any]:
    """Validate and plan a topology. Matrices are empty strings past the DAG depth."""
    if arch not in {"x86_64", "arm64", "both"}:
        raise TopologyError("arch must be x86_64, arm64, or both")
    if isinstance(max_levels, bool) or not isinstance(max_levels, int) or max_levels < 1:
        raise TopologyError("max_levels must be a positive integer")
    nodes, edges, roots = validate_document(document)
    levels = condensation_levels(nodes, edges)
    if len(levels) > max_levels:
        raise TopologyError(
            f"topology needs {len(levels)} levels, but max_levels is {max_levels}"
        )
    matrices: list[dict[str, list[dict[str, str]]] | str] = []
    component_levels: list[list[list[str]]] = []
    for index in range(max_levels):
        if index < len(levels):
            entries = _entries(levels[index], arch)
            matrices.append({"include": entries} if entries else "")
            component_levels.append([list(component) for component in levels[index]])
        else:
            matrices.append("")
            component_levels.append([])
    return {
        "schema_version": SCHEMA_VERSION,
        "arch": arch,
        "roots": roots,
        "levels": component_levels,
        "matrices": matrices,
    }


def write_github_output(plan: dict[str, Any], path: str | os.PathLike[str]) -> None:
    with open(path, "a", encoding="utf-8") as output:
        for index, matrix in enumerate(plan["matrices"], 1):
            value = "" if matrix == "" else json.dumps(matrix, separators=(",", ":"), sort_keys=True)
            output.write(f"level{index}_matrix={value}\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topology", nargs="?", help="kpkg schema v1 JSON file")
    parser.add_argument("--input", dest="input_path", help="alias for the topology file")
    parser.add_argument("--arch", choices=("x86_64", "arm64", "both"), default="both")
    parser.add_argument("--max-levels", type=int, default=DEFAULT_MAX_LEVELS)
    parser.add_argument("--github-output", help="output file (defaults to $GITHUB_OUTPUT)")
    parser.add_argument("--plan-json", help="optional path for the complete plan JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = args.input_path or args.topology
    if not input_path:
        raise TopologyError("a topology JSON file is required")
    if args.input_path and args.topology:
        raise TopologyError("specify the topology either positionally or with --input, not both")
    output_path = args.github_output or os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        raise TopologyError("GITHUB_OUTPUT is not set; use --github-output")
    with open(input_path, encoding="utf-8") as source:
        document = json.load(source)
    plan = plan_document(document, args.arch, args.max_levels)
    write_github_output(plan, output_path)
    if args.plan_json:
        Path(args.plan_json).write_text(
            json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (TopologyError, OSError, json.JSONDecodeError) as error:
        print(f"ci-topology: error: {error}", file=sys.stderr)
        raise SystemExit(2)
