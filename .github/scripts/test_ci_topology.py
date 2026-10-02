#!/usr/bin/env python3
"""Focused tests for the CI topology planner."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("ci-topology.py")
SPEC = importlib.util.spec_from_file_location("ci_topology", SCRIPT)
TOPOLOGY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = TOPOLOGY
SPEC.loader.exec_module(TOPOLOGY)


def document(names, edges=(), roots=()):
    return {
        "schema_version": 1,
        "roots": list(roots),
        "nodes": [{"name": name, "repo": f"/repo/{name}"} for name in names],
        "edges": [
            {"dependency": dependency, "dependent": dependent}
            for dependency, dependent in edges
        ],
    }


class TopologyTests(unittest.TestCase):
    def test_diamond_and_shared_dependencies_use_kahn_levels(self):
        data = document(
            ["app", "left", "right", "base", "other"],
            [("base", "left"), ("base", "right"), ("left", "app"),
             ("right", "app"), ("base", "other")],
            ["app", "other"],
        )
        plan = TOPOLOGY.plan_document(data, "x86_64", 4)
        self.assertEqual(plan["levels"], [
            [["base"]], [["left"], ["other"], ["right"]], [["app"]], []
        ])
        self.assertEqual(plan["matrices"][1], {"include": [
            {"packages": "left"}, {"packages": "other"}, {"packages": "right"}
        ]})
        self.assertEqual(plan["matrices"][3], "")

    def test_disconnected_nodes_are_each_emitted_once(self):
        data = document(["z", "a", "m"], roots=["z"])
        plan = TOPOLOGY.plan_document(data, "x86_64", 2)
        self.assertEqual(plan["levels"], [[[
            "a"], ["m"], ["z"]], []])
        packages = [entry["packages"] for entry in plan["matrices"][0]["include"]]
        self.assertEqual(packages, ["a", "m", "z"])

    def test_cycle_is_one_sorted_matrix_entry(self):
        data = document(
            ["consumer", "cycle-b", "cycle-a"],
            [("cycle-a", "cycle-b"), ("cycle-b", "cycle-a"),
             ("cycle-b", "consumer")],
            ["consumer"],
        )
        plan = TOPOLOGY.plan_document(data, "both", 2)
        self.assertEqual(plan["levels"], [
            [["cycle-a", "cycle-b"]], [["consumer"]]
        ])
        self.assertEqual(plan["matrices"][0]["include"], [
            {"packages": "cycle-a cycle-b"},
            {"packages": "cycle-a cycle-b", "arch": "arm64"},
        ])

    def test_output_is_deterministic_under_reordered_input(self):
        edges = [("a", "c"), ("b", "c"), ("c", "d")]
        first = document(["d", "c", "b", "a"], list(reversed(edges)), ["d"])
        second = document(["a", "b", "c", "d"], edges, ["d"])
        self.assertEqual(
            TOPOLOGY.plan_document(first, "both", 5),
            TOPOLOGY.plan_document(second, "both", 5),
        )

    def test_matrix_limit_accounts_for_arch_expansion(self):
        names = [f"pkg-{index:03}" for index in range(129)]
        with self.assertRaisesRegex(TOPOLOGY.TopologyError, "258 entries"):
            TOPOLOGY.plan_document(document(names), "both", 1)
        plan = TOPOLOGY.plan_document(document(names), "arm64", 1)
        self.assertEqual(len(plan["matrices"][0]["include"]), 129)

    def test_fixed_max_levels_and_overflow(self):
        chain = document(["a", "b", "c"], [("a", "b"), ("b", "c")], ["c"])
        with self.assertRaisesRegex(TOPOLOGY.TopologyError, "needs 3 levels"):
            TOPOLOGY.plan_document(chain, "x86_64", 2)
        empty = TOPOLOGY.plan_document(document([]), "x86_64", 3)
        self.assertEqual(empty["matrices"], ["", "", ""])
        self.assertEqual(empty["levels"], [[], [], []])

    def test_invalid_edges_roots_and_schema_are_rejected(self):
        cases = [
            ({"schema_version": 2, "roots": [], "nodes": [], "edges": []}, "schema_version"),
            ({"schema_version": True, "roots": [], "nodes": [], "edges": []}, "schema_version"),
            (document(["a"], roots=["missing"]), "unknown nodes"),
            (document(["a"], [("a", "missing")]), "unknown nodes"),
            ({"schema_version": 1, "roots": [], "nodes": "bad", "edges": []}, "nodes must be an array"),
            ({"schema_version": 1, "roots": [], "nodes": [{"repo": "x"}], "edges": []}, "name"),
            (document(["a", "a"]), "unique"),
            (document(["a", "b"], [("a", "b"), ("a", "b")]), "edges must be unique"),
        ]
        for data, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(TOPOLOGY.TopologyError, message):
                TOPOLOGY.plan_document(data, "x86_64", 2)

    def test_cli_writes_outputs_and_optional_plan(self):
        data = document(["app", "dep"], [("dep", "app")], ["app"])
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            source, output, saved = temp / "graph.json", temp / "out", temp / "plan.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, SCRIPT, str(source), "--arch", "arm64",
                 "--max-levels", "3", "--github-output", str(output),
                 "--plan-json", str(saved)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = output.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 3)
            self.assertTrue(lines[0].startswith("level1_matrix="))
            self.assertEqual(lines[2], "level3_matrix=")
            matrix = json.loads(lines[0].split("=", 1)[1])
            self.assertEqual(matrix, {"include": [{"arch": "arm64", "packages": "dep"}]})
            self.assertEqual(json.loads(saved.read_text())["roots"], ["app"])


if __name__ == "__main__":
    unittest.main()
