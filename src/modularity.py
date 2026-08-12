"""Dependency-free validator for the Subactor Modularity workspace v1."""

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse


IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
REVISION = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
AUTHORITY = re.compile(r"^authority://[a-z0-9][a-z0-9.-]*(?:/[A-Za-z0-9._~-]+)+$")
LAYER_ORDER = {
    "foundation": 0,
    "domain": 1,
    "application": 2,
    "interface": 3,
    "deployment": 4,
}

ROOT_FIELDS = {
    "$schema",
    "schema",
    "id",
    "version",
    "description",
    "owners",
    "standards",
    "modules",
    "links",
    "policies",
    "analysisScope",
    "conformance",
}
ROOT_REQUIRED = {
    "schema",
    "id",
    "version",
    "owners",
    "standards",
    "modules",
    "links",
    "policies",
    "conformance",
}


class DuplicateKeyError(ValueError):
    """Raised when strict JSON parsing encounters a duplicate object key."""


@dataclasses.dataclass(frozen=True, order=True)
class Finding:
    """One deterministic conformance finding."""

    path: str
    code: str
    message: str
    severity: str = dataclasses.field(compare=False)

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }


def _catalog() -> dict[str, tuple[str, str]]:
    catalog_path = (
        Path(__file__).resolve().parents[1] / "docs" / "errors" / "catalog.json"
    )
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    return {
        item["code"]: (item["severity"], item["message"]) for item in data["errors"]
    }


CATALOG = _catalog()


def _finding(code: str, path: str) -> Finding:
    severity, message = CATALOG[code]
    return Finding(path=path, code=code, message=message, severity=severity)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def load_json_bytes(raw: bytes) -> Any:
    """Parse strict UTF-8 JSON and reject duplicate object keys."""

    text = raw.decode("utf-8", errors="strict")
    return json.loads(text, object_pairs_hook=_unique_object)


def _is_uri(value: Any) -> bool:
    return isinstance(value, str) and bool(urlparse(value).scheme)


def _is_identifier(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= 160
        and bool(IDENTIFIER.fullmatch(value))
    )


def _is_semver(value: Any) -> bool:
    return isinstance(value, str) and bool(SEMVER.fullmatch(value))


def _is_revision(value: Any) -> bool:
    return isinstance(value, str) and bool(REVISION.fullmatch(value))


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and bool(DIGEST.fullmatch(value))


def _is_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or len(value) > 500:
        return False
    if value.startswith("/") or "\\" in value:
        return False
    return ".." not in value.split("/")


def _json_identity(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _glob_covers(outer: str, inner: str) -> bool:
    """Recognize only deterministic, obvious full containment of path globs."""

    if outer in {"*", "**", "**/*"} or outer == inner:
        return True
    if outer.endswith("/**"):
        prefix = outer[:-3].rstrip("/")
        return inner == prefix or inner.startswith(prefix + "/")
    return False


class Validator:
    """Validate a parsed Modularity v1 document without network access."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root.resolve() if root is not None else None
        self.findings: set[Finding] = set()

    def add(self, code: str, path: str) -> None:
        self.findings.add(_finding(code, path))

    def schema(self, path: str) -> None:
        self.add("MOD-SCHEMA-001", path)

    def object_shape(
        self,
        value: Any,
        path: str,
        allowed: set[str],
        required: set[str],
    ) -> bool:
        if not isinstance(value, dict):
            self.schema(path)
            return False
        for key in sorted(set(value) - allowed):
            self.schema(f"{path}.{key}")
        for key in sorted(required - set(value)):
            self.schema(f"{path}.{key}")
        return True

    def identifier(self, value: Any, path: str) -> None:
        if not _is_identifier(value):
            self.schema(path)

    def owners(self, value: Any, path: str) -> None:
        if not isinstance(value, list) or not value:
            self.schema(path)
            return
        identities: list[str] = []
        for index, owner in enumerate(value):
            item_path = f"{path}[{index}]"
            if not self.object_shape(owner, item_path, {"kind", "id"}, {"kind", "id"}):
                continue
            if owner.get("kind") not in {"repository", "team", "person"}:
                self.schema(f"{item_path}.kind")
            if (
                not isinstance(owner.get("id"), str)
                or not owner["id"]
                or len(owner["id"]) > 200
            ):
                self.schema(f"{item_path}.id")
            identities.append(_json_identity(owner))
        if len(identities) != len(set(identities)):
            self.schema(path)

    def standard(self, value: Any, path: str) -> None:
        allowed = {
            "id",
            "relation",
            "status",
            "repository",
            "revision",
            "artifact",
            "note",
        }
        if not self.object_shape(value, path, allowed, {"id", "relation", "status"}):
            return
        self.identifier(value.get("id"), f"{path}.id")
        relation = value.get("relation")
        status = value.get("status")
        if relation not in {"normative", "informative"}:
            self.schema(f"{path}.relation")
        if status not in {"published", "draft"}:
            self.schema(f"{path}.status")
        if "repository" in value and not _is_uri(value["repository"]):
            self.schema(f"{path}.repository")
        if "artifact" in value and not _is_relative_path(value["artifact"]):
            self.add("MOD-PATH-001", f"{path}.artifact")
        if "note" in value and (
            not isinstance(value["note"], str)
            or not value["note"]
            or len(value["note"]) > 1000
        ):
            self.schema(f"{path}.note")
        if relation == "normative":
            if status != "published" or not _is_uri(value.get("repository")):
                self.add("MOD-STANDARD-001", path)
            if not _is_revision(value.get("revision")) or not _is_relative_path(
                value.get("artifact")
            ):
                self.add("MOD-STANDARD-001", path)
        elif "revision" in value and not _is_revision(value["revision"]):
            self.add("MOD-STANDARD-001", f"{path}.revision")
        if status == "draft" and (relation != "informative" or "revision" in value):
            self.add("MOD-STANDARD-001", path)

    def source(self, value: Any, path: str) -> None:
        allowed = {"repository", "revision", "path", "manifest"}
        if not self.object_shape(value, path, allowed, {"repository", "revision"}):
            return
        if not _is_uri(value.get("repository")):
            self.schema(f"{path}.repository")
        if not _is_revision(value.get("revision")):
            self.add("MOD-SOURCE-001", f"{path}.revision")
        for field in ("path", "manifest"):
            if field in value and not _is_relative_path(value[field]):
                self.add("MOD-PATH-001", f"{path}.{field}")

    def contract(self, value: Any, path: str) -> None:
        allowed = {"id", "uri", "kind", "version", "digest", "path"}
        required = {"id", "uri", "kind", "version", "digest"}
        if not self.object_shape(value, path, allowed, required):
            return
        self.identifier(value.get("id"), f"{path}.id")
        if not _is_uri(value.get("uri")):
            self.schema(f"{path}.uri")
        if value.get("kind") not in {
            "dsl",
            "json-schema",
            "protobuf",
            "lifecycle",
            "poa-capability",
            "twin-trait",
            "other",
        }:
            self.schema(f"{path}.kind")
        if not _is_semver(value.get("version")):
            self.schema(f"{path}.version")
        if not _is_digest(value.get("digest")):
            self.schema(f"{path}.digest")
        if "path" in value and not _is_relative_path(value["path"]):
            self.add("MOD-PATH-001", f"{path}.path")

    def state(self, value: Any, path: str) -> None:
        if not isinstance(value, dict):
            self.schema(path)
            return
        role = value.get("role")
        if role == "none":
            self.object_shape(value, path, {"role"}, {"role"})
        elif role == "owner":
            self.object_shape(value, path, {"role", "domain"}, {"role", "domain"})
            self.identifier(value.get("domain"), f"{path}.domain")
        elif role == "projection":
            self.object_shape(
                value,
                path,
                {"role", "domain", "owner"},
                {"role", "domain", "owner"},
            )
            self.identifier(value.get("domain"), f"{path}.domain")
            self.identifier(value.get("owner"), f"{path}.owner")
        else:
            self.schema(f"{path}.role")

    def module(self, value: Any, path: str) -> None:
        allowed = {"id", "owners", "layer", "lifecycle", "source", "state", "contracts"}
        required = allowed
        if not self.object_shape(value, path, allowed, required):
            return
        self.identifier(value.get("id"), f"{path}.id")
        self.owners(value.get("owners"), f"{path}.owners")
        if value.get("layer") not in LAYER_ORDER:
            self.schema(f"{path}.layer")
        if value.get("lifecycle") not in {
            "experimental",
            "stable",
            "deprecated",
            "retired",
        }:
            self.schema(f"{path}.lifecycle")
        self.source(value.get("source"), f"{path}.source")
        self.state(value.get("state"), f"{path}.state")
        contracts = value.get("contracts")
        if not isinstance(contracts, list):
            self.schema(f"{path}.contracts")
        else:
            for index, contract in enumerate(contracts):
                self.contract(contract, f"{path}.contracts[{index}]")

    def link(self, value: Any, path: str) -> None:
        allowed = {"id", "from", "to", "contract", "mode", "authorityRef", "generation"}
        required = {"id", "from", "to", "contract", "mode"}
        if not self.object_shape(value, path, allowed, required):
            return
        for field in ("id", "from", "to"):
            self.identifier(value.get(field), f"{path}.{field}")
        if not _is_uri(value.get("contract")):
            self.schema(f"{path}.contract")
        mode = value.get("mode")
        if mode not in {"link", "generate", "observe", "invoke"}:
            self.schema(f"{path}.mode")
        has_authority = "authorityRef" in value
        if mode == "invoke":
            if (
                not has_authority
                or not isinstance(value.get("authorityRef"), str)
                or not AUTHORITY.fullmatch(value["authorityRef"])
            ):
                self.add("MOD-AUTH-001", f"{path}.authorityRef")
        elif has_authority:
            self.add("MOD-AUTH-001", f"{path}.authorityRef")
        has_generation = "generation" in value
        if mode == "generate":
            generation = value.get("generation")
            if not isinstance(generation, dict):
                self.add("MOD-COMPOSE-001", f"{path}.generation")
            else:
                self.object_shape(
                    generation,
                    f"{path}.generation",
                    {"generator", "outputContract"},
                    {"generator", "outputContract"},
                )
                self.identifier(
                    generation.get("generator"), f"{path}.generation.generator"
                )
                if not _is_uri(generation.get("outputContract")):
                    self.schema(f"{path}.generation.outputContract")
                if not _is_identifier(generation.get("generator")) or not _is_uri(
                    generation.get("outputContract")
                ):
                    self.add("MOD-COMPOSE-001", f"{path}.generation")
        elif has_generation:
            self.add("MOD-COMPOSE-001", f"{path}.generation")

    def policies(self, value: Any, path: str) -> None:
        expected: dict[str, Any] = {
            "unknownFields": "reject",
            "cycles": "reject",
            "layerDirection": "higher-to-same-or-lower",
            "contractOwnership": "single-exporter",
            "stateOwnership": "single-writer",
            "authority": "external-reference-only",
            "twinAuthority": "observational-only",
            "llmAuthority": "propose-only",
        }
        allowed = set(expected) | {"allowDeprecated"}
        if not self.object_shape(value, path, allowed, allowed):
            return
        for field, wanted in expected.items():
            if value.get(field) != wanted:
                self.schema(f"{path}.{field}")
        if not isinstance(value.get("allowDeprecated"), bool):
            self.schema(f"{path}.allowDeprecated")

    def analysis_scope(self, value: Any, path: str) -> None:
        allowed = {
            "includePaths",
            "excludePaths",
            "managedPaths",
            "generatedPaths",
            "llm",
        }
        if not self.object_shape(value, path, allowed, allowed):
            return
        path_lists: dict[str, list[str]] = {}
        for field in ("includePaths", "excludePaths", "managedPaths", "generatedPaths"):
            entries = value.get(field)
            if not isinstance(entries, list) or (
                field == "includePaths" and not entries
            ):
                self.add("MOD-ANALYSIS-001", f"{path}.{field}")
                continue
            path_lists[field] = []
            for index, entry in enumerate(entries):
                if not _is_relative_path(entry):
                    self.add("MOD-PATH-001", f"{path}.{field}[{index}]")
                else:
                    path_lists[field].append(entry)
            if len(path_lists[field]) != len(set(path_lists[field])):
                self.add("MOD-ANALYSIS-001", f"{path}.{field}")
        managed = set(path_lists.get("managedPaths", []))
        generated = set(path_lists.get("generatedPaths", []))
        if managed & generated:
            self.add("MOD-ANALYSIS-001", path)
        includes = path_lists.get("includePaths", [])
        excludes = path_lists.get("excludePaths", [])
        if includes and all(
            any(_glob_covers(exclude, include) for exclude in excludes)
            for include in includes
        ):
            self.add("MOD-ANALYSIS-001", f"{path}.includePaths")
        llm = value.get("llm")
        llm_fields = {
            "inputPolicy",
            "maxPromptTokens",
            "maxFindingsPerBatch",
            "wholeGraphPolicy",
            "requireProvenance",
        }
        if not self.object_shape(llm, f"{path}.llm", llm_fields, llm_fields):
            self.add("MOD-LLM-001", f"{path}.llm")
            return
        valid = (
            llm.get("inputPolicy") == "intent-diff-and-findings"
            and isinstance(llm.get("maxPromptTokens"), int)
            and not isinstance(llm.get("maxPromptTokens"), bool)
            and 4096 <= llm["maxPromptTokens"] <= 200000
            and isinstance(llm.get("maxFindingsPerBatch"), int)
            and not isinstance(llm.get("maxFindingsPerBatch"), bool)
            and 1 <= llm["maxFindingsPerBatch"] <= 200
            and llm.get("wholeGraphPolicy") == "reject"
            and llm.get("requireProvenance") is True
        )
        if not valid:
            self.add("MOD-LLM-001", f"{path}.llm")

    def conformance(self, value: Any, path: str) -> None:
        if not self.object_shape(
            value, path, {"levels", "commands"}, {"levels", "commands"}
        ):
            return
        levels = value.get("levels")
        allowed_levels = {"document", "graph", "standards", "interfaces", "advisory"}
        if (
            not isinstance(levels, list)
            or not levels
            or len(levels) != len(set(item for item in levels if isinstance(item, str)))
            or any(
                not isinstance(item, str) or item not in allowed_levels
                for item in levels
            )
        ):
            self.schema(f"{path}.levels")
        commands = value.get("commands")
        if not isinstance(commands, list) or not commands:
            self.add("MOD-CONFORMANCE-001", f"{path}.commands")
            return
        for index, command in enumerate(commands):
            if (
                not isinstance(command, list)
                or not command
                or any(
                    not isinstance(arg, str) or not arg or len(arg) > 1000
                    for arg in command
                )
            ):
                self.add("MOD-CONFORMANCE-001", f"{path}.commands[{index}]")

    def document_shape(self, document: Any) -> None:
        if not self.object_shape(document, "$", ROOT_FIELDS, ROOT_REQUIRED):
            return
        if document.get("schema") != "subactor.modularity/workspace/v1":
            self.schema("$.schema")
        self.identifier(document.get("id"), "$.id")
        if not _is_semver(document.get("version")):
            self.schema("$.version")
        if "$schema" in document and not _is_uri(document["$schema"]):
            self.schema("$.$schema")
        if "description" in document and (
            not isinstance(document["description"], str)
            or not document["description"]
            or len(document["description"]) > 1000
        ):
            self.schema("$.description")
        self.owners(document.get("owners"), "$.owners")
        standards = document.get("standards")
        if not isinstance(standards, list) or not standards:
            self.schema("$.standards")
        else:
            for index, standard in enumerate(standards):
                self.standard(standard, f"$.standards[{index}]")
            if len([_json_identity(item) for item in standards]) != len(
                set(_json_identity(item) for item in standards)
            ):
                self.schema("$.standards")
        modules = document.get("modules")
        if not isinstance(modules, list) or not modules:
            self.schema("$.modules")
        else:
            for index, module in enumerate(modules):
                self.module(module, f"$.modules[{index}]")
        links = document.get("links")
        if not isinstance(links, list):
            self.schema("$.links")
        else:
            for index, link in enumerate(links):
                self.link(link, f"$.links[{index}]")
        self.policies(document.get("policies"), "$.policies")
        if "analysisScope" in document:
            self.analysis_scope(document["analysisScope"], "$.analysisScope")
        self.conformance(document.get("conformance"), "$.conformance")

    def local_digest(self, contract: dict[str, Any], path: str) -> None:
        relative = contract.get("path")
        digest = contract.get("digest")
        if (
            self.root is None
            or not _is_relative_path(relative)
            or not _is_digest(digest)
        ):
            return
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            self.add("MOD-PATH-001", f"{path}.path")
            return
        if not candidate.is_file():
            return
        observed = "sha256:" + hashlib.sha256(candidate.read_bytes()).hexdigest()
        if observed != digest:
            self.add("MOD-DIGEST-001", f"{path}.digest")

    def semantics(self, document: Any) -> None:
        if not isinstance(document, dict):
            return
        raw_modules = document.get("modules")
        raw_links = document.get("links")
        if not isinstance(raw_modules, list) or not isinstance(raw_links, list):
            return
        modules = [
            item
            for item in raw_modules
            if isinstance(item, dict) and _is_identifier(item.get("id"))
        ]
        links = [item for item in raw_links if isinstance(item, dict)]
        module_paths = {
            id(item): f"$.modules[{index}]"
            for index, item in enumerate(raw_modules)
            if isinstance(item, dict)
        }
        link_paths = {
            id(item): f"$.links[{index}]"
            for index, item in enumerate(raw_links)
            if isinstance(item, dict)
        }

        all_ids = [item.get("id") for item in modules] + [
            item.get("id") for item in links if _is_identifier(item.get("id"))
        ]
        duplicate_ids = {item for item, count in Counter(all_ids).items() if count > 1}
        for module in modules:
            if module.get("id") in duplicate_ids:
                self.add("MOD-ID-001", f"{module_paths[id(module)]}.id")
        for link in links:
            if link.get("id") in duplicate_ids:
                self.add("MOD-ID-001", f"{link_paths[id(link)]}.id")

        module_by_id: dict[str, dict[str, Any]] = {}
        for module in modules:
            module_by_id.setdefault(module["id"], module)

        contracts_by_uri: dict[
            str, list[tuple[dict[str, Any], dict[str, Any], str]]
        ] = defaultdict(list)
        for module in modules:
            module_path = module_paths[id(module)]
            contracts = module.get("contracts")
            if not isinstance(contracts, list):
                continue
            local_ids = [item.get("id") for item in contracts if isinstance(item, dict)]
            duplicate_local = {
                item
                for item, count in Counter(local_ids).items()
                if item is not None and count > 1
            }
            for index, contract in enumerate(contracts):
                if not isinstance(contract, dict):
                    continue
                contract_path = f"{module_path}.contracts[{index}]"
                if contract.get("id") in duplicate_local:
                    self.add("MOD-CONTRACT-001", f"{contract_path}.id")
                uri = contract.get("uri")
                if _is_uri(uri):
                    contracts_by_uri[uri].append((module, contract, contract_path))
                self.local_digest(contract, contract_path)
        for exports in contracts_by_uri.values():
            if len(exports) > 1:
                for _, _, contract_path in exports:
                    self.add("MOD-CONTRACT-001", f"{contract_path}.uri")

        adjacency: dict[str, set[str]] = {
            module_id: set() for module_id in module_by_id
        }
        for link in links:
            link_path = link_paths[id(link)]
            consumer_id = link.get("from")
            provider_id = link.get("to")
            consumer = module_by_id.get(consumer_id)
            provider = module_by_id.get(provider_id)
            if consumer is None:
                self.add("MOD-LINK-001", f"{link_path}.from")
            if provider is None:
                self.add("MOD-LINK-001", f"{link_path}.to")
            if consumer_id == provider_id and consumer is not None:
                self.add("MOD-LINK-002", link_path)
            if consumer is None or provider is None:
                continue
            adjacency[consumer_id].add(provider_id)
            provider_exports = [
                item
                for item in contracts_by_uri.get(link.get("contract"), [])
                if item[0].get("id") == provider_id
            ]
            if len(provider_exports) != 1:
                self.add("MOD-CONTRACT-002", f"{link_path}.contract")
                contract = None
            else:
                contract = provider_exports[0][1]
            consumer_layer = LAYER_ORDER.get(consumer.get("layer"))
            provider_layer = LAYER_ORDER.get(provider.get("layer"))
            if (
                consumer_layer is not None
                and provider_layer is not None
                and consumer_layer < provider_layer
            ):
                self.add("MOD-LAYER-001", link_path)
            lifecycle = provider.get("lifecycle")
            if lifecycle == "retired":
                self.add("MOD-LIFECYCLE-001", link_path)
            if (
                lifecycle == "deprecated"
                and isinstance(document.get("policies"), dict)
                and document["policies"].get("allowDeprecated") is False
            ):
                self.add("MOD-LIFECYCLE-002", link_path)
            if (
                contract is not None
                and contract.get("kind") == "twin-trait"
                and link.get("mode") != "observe"
            ):
                self.add("MOD-TWIN-001", link_path)
            if (
                contract is not None
                and contract.get("kind") == "poa-capability"
                and link.get("mode") != "invoke"
            ):
                self.add("MOD-POA-001", link_path)
        visiting: set[str] = set()
        visited: set[str] = set()
        cyclic: set[str] = set()

        def visit(node: str, trail: list[str]) -> None:
            if node in visiting:
                start = trail.index(node)
                cyclic.update(trail[start:])
                return
            if node in visited:
                return
            visiting.add(node)
            trail.append(node)
            for neighbor in sorted(adjacency.get(node, set())):
                visit(neighbor, trail)
            trail.pop()
            visiting.remove(node)
            visited.add(node)

        for module_id in sorted(adjacency):
            visit(module_id, [])
        for link in links:
            if link.get("from") in cyclic and link.get("to") in cyclic:
                self.add("MOD-GRAPH-001", link_paths[id(link)])

        state_owners: dict[str, list[str]] = defaultdict(list)
        state_domains: set[str] = set()
        for module in modules:
            state = module.get("state")
            if not isinstance(state, dict) or not _is_identifier(state.get("domain")):
                continue
            domain = state["domain"]
            state_domains.add(domain)
            if state.get("role") == "owner":
                state_owners[domain].append(module["id"])
        for domain in state_domains:
            if len(state_owners[domain]) != 1:
                for module in modules:
                    state = module.get("state")
                    if isinstance(state, dict) and state.get("domain") == domain:
                        self.add("MOD-STATE-001", f"{module_paths[id(module)]}.state")
        for module in modules:
            state = module.get("state")
            if not isinstance(state, dict) or state.get("role") != "projection":
                continue
            domain = state.get("domain")
            owners = state_owners.get(domain, [])
            if len(owners) != 1 or state.get("owner") != owners[0]:
                self.add("MOD-STATE-002", f"{module_paths[id(module)]}.state.owner")

        scope = document.get("analysisScope")
        if isinstance(scope, dict):
            excluded = scope.get("excludePaths")
            if isinstance(excluded, list):
                protected_paths: list[str] = []
                for module in modules:
                    source = module.get("source")
                    if isinstance(source, dict) and isinstance(
                        source.get("manifest"), str
                    ):
                        protected_paths.append(source["manifest"])
                    contracts = module.get("contracts")
                    if isinstance(contracts, list):
                        protected_paths.extend(
                            contract["path"]
                            for contract in contracts
                            if isinstance(contract, dict)
                            and isinstance(contract.get("path"), str)
                        )
                if any(
                    fnmatch.fnmatchcase(protected, pattern)
                    for protected in protected_paths
                    for pattern in excluded
                    if isinstance(pattern, str)
                ):
                    self.add("MOD-ANALYSIS-001", "$.analysisScope.excludePaths")

    def validate(self, document: Any) -> list[Finding]:
        self.document_shape(document)
        self.semantics(document)
        return sorted(self.findings)


def validate_document(document: Any, root: Path | None = None) -> list[Finding]:
    return Validator(root=root).validate(document)


def validate_path(path: Path, root: Path | None = None) -> list[Finding]:
    try:
        document = load_json_bytes(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateKeyError):
        return [_finding("MOD-JSON-001", "$")]
    return validate_document(document, root=root)


def render_text(path: Path, findings: Sequence[Finding]) -> str:
    if not findings:
        return f"PASS {path}: document,graph,standards"
    return "\n".join(
        f"{finding.code} {finding.severity} {finding.path}: {finding.message}"
        for finding in findings
    )


def render_json(path: Path, findings: Sequence[Finding]) -> str:
    payload = {
        "schema": "subactor.modularity/validation-report/v1",
        "document": str(path),
        "valid": not findings,
        "findings": [finding.as_dict() for finding in findings],
    }
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="modularity", description=__doc__)
    parser.add_argument(
        "document", type=Path, help="canonical Modularity workspace JSON"
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="optional repository root for digest checks of artifacts that exist locally",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        findings = validate_path(args.document, root=args.root)
        report = (
            render_json(args.document, findings)
            if args.format == "json"
            else render_text(args.document, findings)
        )
        print(report)
        return 1 if findings else 0
    except Exception:
        finding = _finding("MOD-INTERNAL-001", "$")
        report = (
            render_json(args.document, [finding])
            if args.format == "json"
            else render_text(args.document, [finding])
        )
        print(report, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
