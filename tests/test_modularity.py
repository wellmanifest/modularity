from __future__ import annotations

import copy
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import modularity


REVISION = "a" * 40
DIGEST = "sha256:" + "0" * 64


def contract(identifier: str, uri: str, kind: str = "other") -> dict[str, object]:
    return {
        "id": identifier,
        "uri": uri,
        "kind": kind,
        "version": "1.0.0",
        "digest": DIGEST,
    }


def module(
    identifier: str,
    layer: str,
    contracts: list[dict[str, object]],
    state: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "id": identifier,
        "owners": [{"kind": "repository", "id": f"subactor/{identifier}"}],
        "layer": layer,
        "lifecycle": "stable",
        "source": {
            "repository": f"https://github.com/subactor/{identifier}",
            "revision": REVISION,
        },
        "state": state or {"role": "none"},
        "contracts": contracts,
    }


def valid_document() -> dict[str, object]:
    core_uri = "urn:subactor:contract:core:v1"
    twin_uri = "urn:subactor:contract:twin:v1"
    poa_uri = "urn:subactor:contract:poa:v1"
    output_uri = "urn:subactor:contract:generated:v1"
    service_uri = "urn:subactor:contract:service:v1"
    return {
        "$schema": "https://subactor.dev/schemas/modularity-workspace/v1",
        "schema": "subactor.modularity/workspace/v1",
        "id": "subactor.reference",
        "version": "1.0.0",
        "description": "A complete valid test graph.",
        "owners": [{"kind": "team", "id": "subactor"}],
        "standards": [
            {
                "id": "wellmanifest.dsl",
                "relation": "normative",
                "status": "published",
                "repository": "https://github.com/wellmanifest/dsl",
                "revision": "1" * 40,
                "artifact": "docs/DSL.md",
            }
        ],
        "modules": [
            module(
                "core",
                "foundation",
                [contract("core", core_uri, "json-schema")],
                {"role": "owner", "domain": "runtime"},
            ),
            module(
                "twin",
                "foundation",
                [contract("trait", twin_uri, "twin-trait")],
                {"role": "projection", "domain": "runtime", "owner": "core"},
            ),
            module(
                "executor",
                "foundation",
                [contract("capability", poa_uri, "poa-capability")],
            ),
            module("generator", "foundation", [contract("output", output_uri)]),
            module("service", "application", [contract("service", service_uri)]),
        ],
        "links": [
            {
                "id": "service-core",
                "from": "service",
                "to": "core",
                "contract": core_uri,
                "mode": "link",
            },
            {
                "id": "service-twin",
                "from": "service",
                "to": "twin",
                "contract": twin_uri,
                "mode": "observe",
            },
            {
                "id": "service-executor",
                "from": "service",
                "to": "executor",
                "contract": poa_uri,
                "mode": "invoke",
                "authorityRef": "authority://policy/grants/ticket-002",
            },
            {
                "id": "service-generate",
                "from": "service",
                "to": "core",
                "contract": core_uri,
                "mode": "generate",
                "generation": {
                    "generator": "generator",
                    "outputContract": output_uri,
                },
            },
        ],
        "policies": {
            "unknownFields": "reject",
            "cycles": "reject",
            "layerDirection": "higher-to-same-or-lower",
            "contractOwnership": "single-exporter",
            "stateOwnership": "single-writer",
            "authority": "external-reference-only",
            "twinAuthority": "observational-only",
            "llmAuthority": "propose-only",
            "allowDeprecated": False,
        },
        "analysisScope": {
            "includePaths": ["src/**", "docs/**"],
            "excludePaths": ["build/**"],
            "managedPaths": [".governance/**"],
            "generatedPaths": ["dist/**"],
            "llm": {
                "inputPolicy": "intent-diff-and-findings",
                "maxPromptTokens": 32000,
                "maxFindingsPerBatch": 40,
                "wholeGraphPolicy": "reject",
                "requireProvenance": True,
            },
        },
        "conformance": {
            "levels": ["document", "graph", "standards"],
            "commands": [["python", "-m", "modularity", "workspace.json"]],
        },
    }


def codes(document: object, root: Path | None = None) -> set[str]:
    return {
        finding.code for finding in modularity.validate_document(document, root=root)
    }


class DocumentValidationTests(unittest.TestCase):
    def test_complete_workspace_is_valid(self) -> None:
        self.assertEqual(modularity.validate_document(valid_document()), [])

    def test_strict_loader_rejects_duplicate_keys_invalid_utf8_and_bad_json(
        self,
    ) -> None:
        samples = [b'{"schema":"one","schema":"two"}', b"\xff", b'{"schema":']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.json"
            for sample in samples:
                path.write_bytes(sample)
                findings = modularity.validate_path(path)
                self.assertEqual([item.code for item in findings], ["MOD-JSON-001"])

    def test_closed_shape_and_scalar_constraints(self) -> None:
        document = valid_document()
        document["surprise"] = True
        document["version"] = "latest"
        document["conformance"]["levels"] = [["document"]]
        findings = modularity.validate_document(document)
        self.assertIn("MOD-SCHEMA-001", {item.code for item in findings})
        self.assertTrue(all(isinstance(item, modularity.Finding) for item in findings))

    def test_immutable_sources_standards_and_paths(self) -> None:
        document = valid_document()
        document["standards"][0]["revision"] = "main"
        document["modules"][0]["source"]["revision"] = "v1"
        document["modules"][0]["source"]["path"] = "../outside"
        self.assertTrue(
            {"MOD-STANDARD-001", "MOD-SOURCE-001", "MOD-PATH-001"} <= codes(document)
        )

    def test_argv_only_conformance(self) -> None:
        document = valid_document()
        document["conformance"]["commands"] = ["python -m modularity workspace.json"]
        self.assertIn("MOD-CONFORMANCE-001", codes(document))


class GraphValidationTests(unittest.TestCase):
    def test_duplicate_module_link_and_contract_identifiers(self) -> None:
        document = valid_document()
        document["links"][0]["id"] = "core"
        document["modules"][0]["contracts"].append(
            copy.deepcopy(document["modules"][0]["contracts"][0])
        )
        found = codes(document)
        self.assertIn("MOD-ID-001", found)
        self.assertIn("MOD-CONTRACT-001", found)

    def test_unknown_endpoint_and_provider_contract(self) -> None:
        document = valid_document()
        document["links"][0]["from"] = "missing"
        document["links"][1]["contract"] = "urn:missing"
        found = codes(document)
        self.assertIn("MOD-LINK-001", found)
        self.assertIn("MOD-CONTRACT-002", found)

    def test_self_link_cycle_and_upward_layer_dependency(self) -> None:
        document = valid_document()
        service_uri = document["modules"][4]["contracts"][0]["uri"]
        document["links"].append(
            {
                "id": "core-service",
                "from": "core",
                "to": "service",
                "contract": service_uri,
                "mode": "link",
            }
        )
        document["links"].append(
            {
                "id": "core-self",
                "from": "core",
                "to": "core",
                "contract": document["modules"][0]["contracts"][0]["uri"],
                "mode": "link",
            }
        )
        found = codes(document)
        self.assertTrue({"MOD-LINK-002", "MOD-GRAPH-001", "MOD-LAYER-001"} <= found)

    def test_state_owner_and_projection_must_resolve(self) -> None:
        document = valid_document()
        document["modules"][1]["state"]["owner"] = "executor"
        self.assertIn("MOD-STATE-002", codes(document))
        document["modules"][0]["state"] = {"role": "none"}
        found = codes(document)
        self.assertTrue({"MOD-STATE-001", "MOD-STATE-002"} <= found)

    def test_lifecycle_policy_rejects_retired_and_disallowed_deprecated(self) -> None:
        retired = valid_document()
        retired["modules"][0]["lifecycle"] = "retired"
        self.assertIn("MOD-LIFECYCLE-001", codes(retired))
        deprecated = valid_document()
        deprecated["modules"][0]["lifecycle"] = "deprecated"
        self.assertIn("MOD-LIFECYCLE-002", codes(deprecated))
        deprecated["policies"]["allowDeprecated"] = True
        self.assertNotIn("MOD-LIFECYCLE-002", codes(deprecated))

    def test_twin_poa_and_authority_boundaries(self) -> None:
        document = valid_document()
        document["links"][1]["mode"] = "link"
        document["links"][1]["authorityRef"] = "authority://policy/bad"
        document["links"][2]["mode"] = "link"
        found = codes(document)
        self.assertTrue({"MOD-TWIN-001", "MOD-POA-001", "MOD-AUTH-001"} <= found)

    def test_generation_provenance_resolves_generator_output(self) -> None:
        document = valid_document()
        del document["links"][3]["generation"]
        self.assertIn("MOD-COMPOSE-001", codes(document))


class IntegrityAndReportingTests(unittest.TestCase):
    def test_local_existing_artifact_digest_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "contract.json"
            artifact.write_bytes(b'{"stable":true}\n')
            document = valid_document()
            item = document["modules"][0]["contracts"][0]
            item["path"] = "contract.json"
            item["digest"] = (
                "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
            )
            self.assertNotIn("MOD-DIGEST-001", codes(document, root))
            item["digest"] = DIGEST
            self.assertIn("MOD-DIGEST-001", codes(document, root))

    def test_missing_remote_artifact_is_not_fabricated_as_a_digest_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = valid_document()
            document["modules"][0]["contracts"][0]["path"] = "remote/contract.json"
            self.assertNotIn("MOD-DIGEST-001", codes(document, Path(directory)))

    def test_analysis_scope_rejects_overlap_hidden_contract_and_bad_llm_policy(
        self,
    ) -> None:
        document = valid_document()
        document["modules"][0]["contracts"][0]["path"] = "docs/core.json"
        scope = document["analysisScope"]
        scope["excludePaths"] = ["docs/**"]
        scope["managedPaths"] = ["dist/**"]
        scope["llm"]["wholeGraphPolicy"] = "allow"
        found = codes(document)
        self.assertTrue({"MOD-ANALYSIS-001", "MOD-LLM-001"} <= found)

        document = valid_document()
        document["analysisScope"]["excludePaths"] = ["**"]
        self.assertIn("MOD-ANALYSIS-001", codes(document))

    def test_findings_and_json_report_are_deterministic(self) -> None:
        document = valid_document()
        document["links"][0]["from"] = "missing"
        document["links"][1]["contract"] = "urn:missing"
        first = modularity.validate_document(document)
        second = modularity.validate_document(copy.deepcopy(document))
        self.assertEqual(first, second)
        self.assertEqual(first, sorted(first))
        payload = json.loads(modularity.render_json(Path("workspace.json"), first))
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["findings"], [item.as_dict() for item in first])

    def test_cli_exit_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.json"
            path.write_text(json.dumps(valid_document()), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(modularity.main([str(path), "--format", "json"]), 0)
            self.assertTrue(json.loads(output.getvalue())["valid"])

            path.write_text("{}", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(modularity.main([str(path), "--format", "json"]), 1)
            self.assertFalse(json.loads(output.getvalue())["valid"])

    def test_unexpected_failure_is_exit_two(self) -> None:
        error = io.StringIO()
        with mock.patch("modularity.validate_path", side_effect=RuntimeError("boom")):
            with redirect_stderr(error):
                self.assertEqual(modularity.main(["workspace.json"]), 2)
        self.assertIn("MOD-INTERNAL-001", error.getvalue())


if __name__ == "__main__":
    unittest.main()
