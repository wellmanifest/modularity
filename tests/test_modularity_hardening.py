"""Adversarial SCC cycle, unhashable field, and bounded JSON I/O regression tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_modularity import contract, module, valid_document

import modularity
import modularity_io


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
            {
                "id": "l-bx",
                "from": "b-join",
                "to": "x-node",
                "contract": "urn:subactor:x",
                "mode": "link",
            },
            {
                "id": "l-xm",
                "from": "x-node",
                "to": "m-first",
                "contract": "urn:subactor:m",
                "mode": "link",
            },
            {
                "id": "l-mb",
                "from": "m-first",
                "to": "b-join",
                "contract": "urn:subactor:b",
                "mode": "link",
            },
            {
                "id": "l-xn",
                "from": "x-node",
                "to": "n-second",
                "contract": "urn:subactor:n",
                "mode": "link",
            },
            {
                "id": "l-nm",
                "from": "n-second",
                "to": "m-first",
                "contract": "urn:subactor:m",
                "mode": "link",
            },
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
            {
                "id": "l1",
                "from": "c1a",
                "to": "c1b",
                "contract": "urn:subactor:c1b",
                "mode": "link",
            },
            {
                "id": "l2",
                "from": "c1b",
                "to": "c1a",
                "contract": "urn:subactor:c1a",
                "mode": "link",
            },
            {
                "id": "bridge",
                "from": "c1a",
                "to": "c2a",
                "contract": "urn:subactor:c2a",
                "mode": "link",
            },
            {
                "id": "l3",
                "from": "c2a",
                "to": "c2b",
                "contract": "urn:subactor:c2b",
                "mode": "link",
            },
            {
                "id": "l4",
                "from": "c2b",
                "to": "c2a",
                "contract": "urn:subactor:c2a",
                "mode": "link",
            },
        ]
        findings = modularity.validate_document(doc)
        cycle_paths = {f.path for f in findings if f.code == "MOD-GRAPH-001"}
        self.assertEqual(
            cycle_paths, {"$.links[0]", "$.links[1]", "$.links[3]", "$.links[4]"}
        )
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

    def test_unhashable_and_heterogeneous_fields_emit_findings_without_type_error(
        self,
    ) -> None:
        doc = valid_document()
        doc["owners"][0]["kind"] = ["team"]
        doc["standards"][0]["relation"] = ["normative"]
        doc["standards"][0]["status"] = ["published"]
        doc["modules"][0]["contracts"][0]["id"] = ["unhashable-id"]
        doc["modules"][0]["contracts"][0]["kind"] = ["dsl"]
        doc["modules"][0]["layer"] = ["not-a-layer"]
        doc["modules"][1]["state"] = {
            "role": "projection",
            "domain": ["bad"],
            "owner": ["bad"],
        }
        doc["links"][0]["from"] = ["bad-from"]
        doc["links"][0]["to"] = {"bad": "to"}
        doc["links"][1]["contract"] = ["bad-contract"]
        doc["links"][3]["generation"] = {
            "generator": ["bad"],
            "outputContract": ["bad"],
        }
        doc["standards"].append({1: "non-string-key"})
        findings = modularity.validate_document(doc)
        self.assertIn("MOD-SCHEMA-001", {f.code for f in findings})
        self.assertNotIn("MOD-INTERNAL-001", {f.code for f in findings})

    def test_json_loader_rejects_float_overflow_and_intra_root_symlink_contract_paths(
        self,
    ) -> None:
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

    def test_json_loader_rejects_nan_infinity_deep_nesting_symlinks_and_fifos(
        self,
    ) -> None:
        for payload in (
            b'{"a": NaN}',
            b'{"a": Infinity}',
            b'{"a": -Infinity}',
            b"[" * (modularity.MAX_JSON_DEPTH + 5)
            + b"]" * (modularity.MAX_JSON_DEPTH + 5),
        ):
            with self.assertRaises(ValueError):
                modularity.load_json_bytes(payload)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real.json"
            real.write_bytes(b"{}")
            sym = root / "sym.json"
            sym.symlink_to(real)
            self.assertEqual(
                [f.code for f in modularity.validate_path(sym)], ["MOD-JSON-001"]
            )

            deep = root / "deep.json"
            deep.write_bytes(b"[" * 2000 + b"]" * 2000)
            self.assertEqual(
                [f.code for f in modularity.validate_path(deep)], ["MOD-JSON-001"]
            )

            if hasattr(os, "mkfifo"):
                fifo = root / "pipe.json"
                os.mkfifo(fifo)
                self.assertEqual(
                    [f.code for f in modularity.validate_path(fifo)], ["MOD-JSON-001"]
                )
                doc = valid_document()
                doc["modules"][0]["contracts"][0]["path"] = "pipe.json"
                found = {f.code for f in modularity.validate_document(doc, root=root)}
                self.assertIn("MOD-PATH-001", found)

    def test_inode_swap_ancestor_symlink_uri_dotdot_drive_paths_and_regex_anchors(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_dir = root / "real_dir"
            real_dir.mkdir()
            doc_file = real_dir / "workspace.json"
            doc_file.write_bytes(b"{}")
            sym_dir = root / "sym_dir"
            sym_dir.symlink_to(real_dir)
            self.assertEqual(
                [
                    f.code
                    for f in modularity.validate_path(
                        sym_dir / "workspace.json", root=root
                    )
                ],
                ["MOD-JSON-001"],
            )

            real_fstat = os.fstat

            def swapped_fstat(fd: int) -> os.stat_result:
                st = real_fstat(fd)
                return os.stat_result(
                    (
                        st.st_mode,
                        st.st_ino + 1,
                        st.st_dev,
                        st.st_nlink,
                        st.st_uid,
                        st.st_gid,
                        st.st_size,
                        st.st_atime,
                        st.st_mtime,
                        st.st_ctime,
                    )
                )

            with (
                mock.patch.object(modularity_io.os, "fstat", side_effect=swapped_fstat),
                self.assertRaises(OSError),
            ):
                modularity.read_regular_file_bytes(doc_file)

        for bad_uri in (
            "https://example.test/../escape",
            "https://example.test/./escape",
            "urn:subactor:../escape",
            "urn:subactor:./escape",
            "urn:subactor:",
            "urn:subactor::v1",
            "http:///missing-host",
            "https://example.test/\ud800",
        ):
            self.assertFalse(modularity._is_uri(bad_uri), bad_uri)
        self.assertFalse(modularity._is_relative_path("C:foo/bar"))
        self.assertFalse(modularity._is_relative_path("docs/\ud800.json"))
        self.assertIsNone(modularity.REVISION.match("a" * 40 + "\n"))
        self.assertIsNone(modularity.SEMVER.match("1.0.0\n"))

    def test_json_int_overflow_surrogates_rootless_ancestor_symlinks_and_anchors(
        self,
    ) -> None:
        for bad_json in (
            b'{"n": ' + b"1" + (b"0" * 400) + b"}",
            b'{"n": -' + b"1" + (b"0" * 400) + b"}",
            b'{"n": ' + (b"9" * 5000) + b"}",
            b'{"a": "\\ud800"}',
            b'{"\\udfff": 1}',
        ):
            with self.subTest(sample=bad_json[:24]), self.assertRaises(ValueError):
                modularity.load_json_bytes(bad_json)

        doc = valid_document()
        doc["description"] = "bad \ud800 surrogate"
        doc["owners"][0]["id"] = "team-\udfff"
        doc["links"][2]["authorityRef"] = "authority://policy/../grants"
        found = {(f.code, f.path) for f in modularity.validate_document(doc)}
        self.assertIn(("MOD-SCHEMA-001", "$.description"), found)
        self.assertIn(("MOD-SCHEMA-001", "$.owners[0].id"), found)
        self.assertIn(("MOD-AUTH-001", "$.links[2].authorityRef"), found)
        self.assertIsNone(modularity.AUTHORITY.fullmatch("authority://policy/./grants"))

        for pattern in (
            modularity.IDENTIFIER,
            modularity.URI_SCHEME,
            modularity.SEMVER,
            modularity.REVISION,
            modularity.DIGEST,
            modularity.AUTHORITY,
            modularity.WINDOWS_DRIVE_PREFIX,
        ):
            self.assertTrue(pattern.pattern.startswith(r"\A"), pattern.pattern)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_dir = root / "real_dir" / "sub"
            real_dir.mkdir(parents=True)
            doc_file = real_dir / "workspace.json"
            doc_file.write_bytes(b"0123456789")
            sym_dir = root / "sym_dir"
            sym_dir.symlink_to(root / "real_dir")
            self.assertEqual(
                [
                    f.code
                    for f in modularity.validate_path(
                        sym_dir / "sub" / "workspace.json"
                    )
                ],
                ["MOD-JSON-001"],
            )
            for bad_max in (0, -1, True, False):
                with self.assertRaises(ValueError):
                    modularity.read_regular_file_bytes(doc_file, max_bytes=bad_max)  # type: ignore[arg-type]
                with self.assertRaises(ValueError):
                    modularity.load_json_bytes(b"{}", max_bytes=bad_max)  # type: ignore[arg-type]
            with self.assertRaises(OSError):
                modularity.read_regular_file_bytes(doc_file, max_bytes=5)

    def test_modularity_io_extraction_relative_symlink_traversal_digit_bounds_and_control_chars(
        self,
    ) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        for folder in ("src", "tests"):
            for py_file in sorted((repo_root / folder).glob("*.py")):
                line_count = len(py_file.read_text(encoding="utf-8").splitlines())
                self.assertLess(
                    line_count, 500, f"{py_file.name} exceeded 500 lines ({line_count})"
                )

        self.assertIs(
            modularity.read_regular_file_bytes, modularity_io.read_regular_file_bytes
        )
        self.assertIs(modularity.load_json_bytes, modularity_io.load_json_bytes)
        self.assertIs(
            modularity._valid_single_line_str, modularity_io._valid_single_line_str
        )

        for bad_json in (
            b'{"n": ' + (b"1" * 401) + b"}",
            b'{"n": -' + (b"9" * 10000) + b"}",
        ):
            with self.assertRaises(ValueError):
                modularity.load_json_bytes(bad_json)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            real_dir = root / "real_dir"
            sub_dir = root / "sub_dir"
            real_dir.mkdir()
            sub_dir.mkdir()
            target = real_dir / "workspace.json"
            target.write_bytes(b"{}")
            sym_dir = root / "sym_dir"
            sym_dir.symlink_to(real_dir)

            with self.assertRaises(OSError):
                modularity.read_regular_file_bytes(
                    Path(f"{sym_dir}/../real_dir/workspace.json")
                )

            prev_cwd = Path.cwd()
            try:
                os.chdir(root)
                for rel_bad in (
                    Path("sym_dir/workspace.json"),
                    Path("sym_dir/../real_dir/workspace.json"),
                ):
                    with self.subTest(rel_bad=str(rel_bad)), self.assertRaises(OSError):
                        modularity.read_regular_file_bytes(rel_bad)
                os.chdir(sub_dir)
                for rel_bad in (
                    Path("../sym_dir/workspace.json"),
                    Path("../sym_dir/../real_dir/workspace.json"),
                ):
                    with self.subTest(rel_bad=str(rel_bad)), self.assertRaises(OSError):
                        modularity.read_regular_file_bytes(rel_bad)
                self.assertEqual(
                    modularity.read_regular_file_bytes(
                        Path("../real_dir/workspace.json")
                    ),
                    b"{}",
                )
            finally:
                os.chdir(prev_cwd)

        doc = valid_document()
        doc["description"] = "multi-line\n\tallowed"
        doc["standards"][0]["note"] = "prose\n\tallowed"
        self.assertEqual(modularity.validate_document(doc), [])

        bad_doc = valid_document()
        bad_doc["description"] = "null\x00byte"
        bad_doc["owners"][0]["id"] = "team\r\ninject"
        bad_doc["standards"][0]["note"] = "del\x7fchar"
        bad_doc["conformance"]["commands"] = [["python3", "-m\ninject"]]
        found = {(f.code, f.path) for f in modularity.validate_document(bad_doc)}
        self.assertIn(("MOD-SCHEMA-001", "$.description"), found)
        self.assertIn(("MOD-SCHEMA-001", "$.owners[0].id"), found)
        self.assertIn(("MOD-SCHEMA-001", "$.standards[0].note"), found)
        self.assertIn(("MOD-CONFORMANCE-001", "$.conformance.commands[0]"), found)

        surrogate_doc = valid_document()
        surrogate_doc["standards"][0]["note"] = "lone-\ud800-surrogate"
        surrogate_doc["conformance"]["commands"] = [["python3", "arg-\udfff"]]
        found_surr = {
            (f.code, f.path) for f in modularity.validate_document(surrogate_doc)
        }
        self.assertIn(("MOD-SCHEMA-001", "$.standards[0].note"), found_surr)
        self.assertIn(("MOD-CONFORMANCE-001", "$.conformance.commands[0]"), found_surr)


if __name__ == "__main__":
    unittest.main()
