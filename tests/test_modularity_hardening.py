"""Adversarial SCC cycle, unhashable field, and bounded JSON I/O regression tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from test_modularity import contract, module, valid_document

import modularity


class HardeningRegressionTests(unittest.TestCase):
    def test_tarjan_scc_catches_secondary_cycle_branch_via_visited_node(self) -> None:
        doc = valid_document()
        doc["modules"] = [
            module("b-join", "foundation", [contract("cb", "urn:subactor:b")]),
            module("m-first", "foundation", [contract("cm", "urn:subactor:m")]),
            module("n-second", "foundation", [contract("cn", "urn:subactor:n")]),
            module("x-node", "foundation", [contract("cx", "urn:subactor:x")]),
        ]
        doc["links"] = [
            {"id": "l-bx", "from": "b-join", "to": "x-node", "contract": "urn:subactor:x", "mode": "link"},
            {"id": "l-xm", "from": "x-node", "to": "m-first", "contract": "urn:subactor:m", "mode": "link"},
            {"id": "l-mb", "from": "m-first", "to": "b-join", "contract": "urn:subactor:b", "mode": "link"},
            {"id": "l-xn", "from": "x-node", "to": "n-second", "contract": "urn:subactor:n", "mode": "link"},
            {"id": "l-nm", "from": "n-second", "to": "m-first", "contract": "urn:subactor:m", "mode": "link"},
        ]
        findings = modularity.validate_document(doc)
        cycle_paths = {f.path for f in findings if f.code == "MOD-GRAPH-001"}
        self.assertEqual(
            cycle_paths,
            {"$.links[0]", "$.links[1]", "$.links[2]", "$.links[3]", "$.links[4]"},
        )

    def test_tarjan_scc_does_not_flag_bridge_between_disjoint_cycles(self) -> None:
        doc = valid_document()
        doc["modules"] = [
            module("c1a", "application", [contract("c1a", "urn:subactor:c1a")]),
            module("c1b", "application", [contract("c1b", "urn:subactor:c1b")]),
            module("c2a", "foundation", [contract("c2a", "urn:subactor:c2a")]),
            module("c2b", "foundation", [contract("c2b", "urn:subactor:c2b")]),
        ]
        doc["links"] = [
            {"id": "l1", "from": "c1a", "to": "c1b", "contract": "urn:subactor:c1b", "mode": "link"},
            {"id": "l2", "from": "c1b", "to": "c1a", "contract": "urn:subactor:c1a", "mode": "link"},
            {"id": "bridge", "from": "c1a", "to": "c2a", "contract": "urn:subactor:c2a", "mode": "link"},
            {"id": "l3", "from": "c2a", "to": "c2b", "contract": "urn:subactor:c2b", "mode": "link"},
            {"id": "l4", "from": "c2b", "to": "c2a", "contract": "urn:subactor:c2a", "mode": "link"},
        ]
        findings = modularity.validate_document(doc)
        cycle_paths = {f.path for f in findings if f.code == "MOD-GRAPH-001"}
        self.assertEqual(cycle_paths, {"$.links[0]", "$.links[1]", "$.links[3]", "$.links[4]"})
        self.assertNotIn("$.links[2]", cycle_paths)

    def test_deep_linear_module_chain_does_not_hit_recursion_limit(self) -> None:
        doc = valid_document()
        count = 1500
        doc["modules"] = [
            module(f"m{i}", "foundation", [contract(f"c{i}", f"urn:subactor:m{i}")])
            for i in range(count)
        ]
        doc["links"] = [
            {
                "id": f"l{i}",
                "from": f"m{i}",
                "to": f"m{i + 1}",
                "contract": f"urn:subactor:m{i + 1}",
                "mode": "link",
            }
            for i in range(count - 1)
        ]
        self.assertEqual(modularity.validate_document(doc), [])

    def test_unhashable_and_heterogeneous_fields_emit_findings_without_type_error(self) -> None:
        doc = valid_document()
        doc["owners"][0]["kind"] = ["team"]
        doc["standards"][0]["relation"] = ["normative"]
        doc["standards"][0]["status"] = ["published"]
        doc["modules"][0]["contracts"][0]["id"] = ["unhashable-id"]
        doc["modules"][0]["contracts"][0]["kind"] = ["dsl"]
        doc["modules"][0]["layer"] = ["not-a-layer"]
        doc["modules"][1]["state"] = {"role": "projection", "domain": ["bad"], "owner": ["bad"]}
        doc["links"][0]["from"] = ["bad-from"]
        doc["links"][0]["to"] = {"bad": "to"}
        doc["links"][1]["contract"] = ["bad-contract"]
        doc["links"][3]["generation"] = {"generator": ["bad"], "outputContract": ["bad"]}
        doc["standards"].append({1: "non-string-key"})
        findings = modularity.validate_document(doc)
        self.assertIn("MOD-SCHEMA-001", {f.code for f in findings})
        self.assertNotIn("MOD-INTERNAL-001", {f.code for f in findings})

    def test_json_loader_rejects_float_overflow_and_intra_root_symlink_contract_paths(self) -> None:
        for payload in (b'{"a": 1e999}', b'{"a": -1e999}'):
            with self.assertRaises(ValueError):
                modularity.load_json_bytes(payload)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real_contract.json"
            real.write_bytes(b'{"ok": true}')
            intra_sym = root / "linked_contract.json"
            intra_sym.symlink_to(real)

            doc = valid_document()
            doc["modules"][0]["contracts"][0]["path"] = "linked_contract.json"
            found = {f.code for f in modularity.validate_document(doc, root=root)}
            self.assertIn("MOD-PATH-001", found)

            sub_dir = root / "real_dir"
            sub_dir.mkdir()
            (sub_dir / "nested.json").write_bytes(b'{"ok": true}')
            sym_dir = root / "sym_dir"
            sym_dir.symlink_to(sub_dir)
            doc2 = valid_document()
            doc2["modules"][0]["contracts"][0]["path"] = "sym_dir/nested.json"
            found2 = {f.code for f in modularity.validate_document(doc2, root=root)}
            self.assertIn("MOD-PATH-001", found2)

    def test_json_loader_rejects_nan_infinity_deep_nesting_symlinks_and_fifos(self) -> None:
        for payload in (
            b'{"a": NaN}',
            b'{"a": Infinity}',
            b'{"a": -Infinity}',
            b"[" * (modularity.MAX_JSON_DEPTH + 5) + b"]" * (modularity.MAX_JSON_DEPTH + 5),
        ):
            with self.assertRaises(ValueError):
                modularity.load_json_bytes(payload)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real.json"
            real.write_bytes(b"{}")
            sym = root / "sym.json"
            sym.symlink_to(real)
            self.assertEqual([f.code for f in modularity.validate_path(sym)], ["MOD-JSON-001"])

            deep = root / "deep.json"
            deep.write_bytes(b"[" * 2000 + b"]" * 2000)
            self.assertEqual([f.code for f in modularity.validate_path(deep)], ["MOD-JSON-001"])

            if hasattr(os, "mkfifo"):
                fifo = root / "pipe.json"
                os.mkfifo(fifo)
                self.assertEqual([f.code for f in modularity.validate_path(fifo)], ["MOD-JSON-001"])
                doc = valid_document()
                doc["modules"][0]["contracts"][0]["path"] = "pipe.json"
                found = {f.code for f in modularity.validate_document(doc, root=root)}
                self.assertIn("MOD-PATH-001", found)


if __name__ == "__main__":
    unittest.main()
