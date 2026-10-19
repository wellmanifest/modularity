"""Graph, contract, layer, cycle, and state semantic validation for Modularity v1."""

from __future__ import annotations

import fnmatch
import hashlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import re

IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
LAYER_ORDER = {
    "foundation": 0,
    "domain": 1,
    "application": 2,
    "interface": 3,
    "deployment": 4,
}


def _is_uri(value: Any) -> bool:
    return isinstance(value, str) and bool(urlparse(value).scheme)


def _is_identifier(value: Any) -> bool:
    return isinstance(value, str) and len(value) <= 160 and bool(IDENTIFIER.fullmatch(value))


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and bool(DIGEST.fullmatch(value))


def _is_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or len(value) > 500:
        return False
    if value.startswith("/") or "\\" in value:
        return False
    return ".." not in value.split("/")


def check_local_digest(validator: Any, contract: dict[str, Any], path: str) -> None:
    relative = contract.get("path")
    digest = contract.get("digest")
    if validator.root is None or not _is_relative_path(relative) or not _is_digest(digest):
        return
    candidate = (validator.root / relative).resolve()
    try:
        candidate.relative_to(validator.root)
    except ValueError:
        validator.add("MOD-PATH-001", f"{path}.path")
        return
    if not candidate.is_file():
        return
    observed = "sha256:" + hashlib.sha256(candidate.read_bytes()).hexdigest()
    if observed != digest:
        validator.add("MOD-DIGEST-001", f"{path}.digest")


def evaluate_semantics(validator: Any, document: Any) -> None:
    if not isinstance(document, dict):
        return
    raw_modules = document.get("modules")
    raw_links = document.get("links")
    if not isinstance(raw_modules, list) or not isinstance(raw_links, list):
        return
    modules = [item for item in raw_modules if isinstance(item, dict) and _is_identifier(item.get("id"))]
    links = [item for item in raw_links if isinstance(item, dict)]
    module_paths = {id(item): f"$.modules[{index}]" for index, item in enumerate(raw_modules) if isinstance(item, dict)}
    link_paths = {id(item): f"$.links[{index}]" for index, item in enumerate(raw_links) if isinstance(item, dict)}

    all_ids = [item.get("id") for item in modules] + [item.get("id") for item in links if _is_identifier(item.get("id"))]
    duplicate_ids = {item for item, count in Counter(all_ids).items() if count > 1}
    for module in modules:
        if module.get("id") in duplicate_ids:
            validator.add("MOD-ID-001", f"{module_paths[id(module)]}.id")
    for link in links:
        if link.get("id") in duplicate_ids:
            validator.add("MOD-ID-001", f"{link_paths[id(link)]}.id")

    module_by_id: dict[str, dict[str, Any]] = {}
    for module in modules:
        module_by_id.setdefault(module["id"], module)

    contracts_by_uri: dict[str, list[tuple[dict[str, Any], dict[str, Any], str]]] = defaultdict(list)
    for module in modules:
        module_path = module_paths[id(module)]
        contracts = module.get("contracts")
        if not isinstance(contracts, list):
            continue
        local_ids = [item.get("id") for item in contracts if isinstance(item, dict)]
        duplicate_local = {item for item, count in Counter(local_ids).items() if item is not None and count > 1}
        for index, contract in enumerate(contracts):
            if not isinstance(contract, dict):
                continue
            contract_path = f"{module_path}.contracts[{index}]"
            if contract.get("id") in duplicate_local:
                validator.add("MOD-CONTRACT-001", f"{contract_path}.id")
            uri = contract.get("uri")
            if _is_uri(uri):
                contracts_by_uri[uri].append((module, contract, contract_path))
            validator.local_digest(contract, contract_path)
    for exports in contracts_by_uri.values():
        if len(exports) > 1:
            for _, _, contract_path in exports:
                validator.add("MOD-CONTRACT-001", f"{contract_path}.uri")

    adjacency: dict[str, set[str]] = {module_id: set() for module_id in module_by_id}
    for link in links:
        link_path = link_paths[id(link)]
        consumer_id = link.get("from")
        provider_id = link.get("to")
        consumer = module_by_id.get(consumer_id)
        provider = module_by_id.get(provider_id)
        if consumer is None:
            validator.add("MOD-LINK-001", f"{link_path}.from")
        if provider is None:
            validator.add("MOD-LINK-001", f"{link_path}.to")
        if consumer_id == provider_id and consumer is not None:
            validator.add("MOD-LINK-002", link_path)
        if consumer is None or provider is None:
            continue
        adjacency[consumer_id].add(provider_id)
        provider_exports = [item for item in contracts_by_uri.get(link.get("contract"), []) if item[0].get("id") == provider_id]
        if len(provider_exports) != 1:
            validator.add("MOD-CONTRACT-002", f"{link_path}.contract")
            contract = None
        else:
            contract = provider_exports[0][1]
        consumer_layer = LAYER_ORDER.get(consumer.get("layer"))
        provider_layer = LAYER_ORDER.get(provider.get("layer"))
        if consumer_layer is not None and provider_layer is not None and consumer_layer < provider_layer:
            validator.add("MOD-LAYER-001", link_path)
        lifecycle = provider.get("lifecycle")
        if lifecycle == "retired":
            validator.add("MOD-LIFECYCLE-001", link_path)
        if lifecycle == "deprecated" and isinstance(document.get("policies"), dict) and document["policies"].get("allowDeprecated") is False:
            validator.add("MOD-LIFECYCLE-002", link_path)
        if contract is not None and contract.get("kind") == "twin-trait" and link.get("mode") != "observe":
            validator.add("MOD-TWIN-001", link_path)
        if contract is not None and contract.get("kind") == "poa-capability" and link.get("mode") != "invoke":
            validator.add("MOD-POA-001", link_path)
        generation = link.get("generation")
        if link.get("mode") == "generate" and isinstance(generation, dict):
            output_exports = contracts_by_uri.get(generation.get("outputContract"), [])
            if len(output_exports) != 1:
                validator.add("MOD-COMPOSE-001", f"{link_path}.generation.outputContract")

    visiting: set[str] = set()
    visited: set[str] = set()
    cyclic: set[str] = set()

    def visit(node: str, trail: list[str]) -> None:
        if node in visiting:
            cyclic.update(trail[trail.index(node):])
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
            validator.add("MOD-GRAPH-001", link_paths[id(link)])

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
                    validator.add("MOD-STATE-001", f"{module_paths[id(module)]}.state")
    for module in modules:
        state = module.get("state")
        if not isinstance(state, dict) or state.get("role") != "projection":
            continue
        domain = state.get("domain")
        owners = state_owners.get(domain, [])
        if len(owners) != 1 or state.get("owner") != owners[0]:
            validator.add("MOD-STATE-002", f"{module_paths[id(module)]}.state.owner")

    scope = document.get("analysisScope")
    if isinstance(scope, dict) and isinstance(scope.get("excludePaths"), list):
        excluded = scope["excludePaths"]
        protected_paths: list[str] = []
        for module in modules:
            source = module.get("source")
            if isinstance(source, dict) and isinstance(source.get("manifest"), str):
                protected_paths.append(source["manifest"])
            contracts = module.get("contracts")
            if isinstance(contracts, list):
                protected_paths.extend(
                    c["path"] for c in contracts if isinstance(c, dict) and isinstance(c.get("path"), str)
                )
        if any(fnmatch.fnmatchcase(p, pat) for p in protected_paths for pat in excluded if isinstance(pat, str)):
            validator.add("MOD-ANALYSIS-001", "$.analysisScope.excludePaths")


def _glob_covers(outer: str, inner: str) -> bool:
    if outer in {"*", "**", "**/*"} or outer == inner:
        return True
    if outer.endswith("/**"):
        prefix = outer[:-3].rstrip("/")
        return inner == prefix or inner.startswith(prefix + "/")
    return False


def check_analysis_scope(validator: Any, value: Any, path: str) -> None:
    allowed = {"includePaths", "excludePaths", "managedPaths", "generatedPaths", "llm"}
    if not validator.object_shape(value, path, allowed, allowed):
        return
    path_lists: dict[str, list[str]] = {}
    for field in ("includePaths", "excludePaths", "managedPaths", "generatedPaths"):
        entries = value.get(field)
        if not isinstance(entries, list) or (field == "includePaths" and not entries):
            validator.add("MOD-ANALYSIS-001", f"{path}.{field}")
            continue
        path_lists[field] = []
        for index, entry in enumerate(entries):
            if not _is_relative_path(entry):
                validator.add("MOD-PATH-001", f"{path}.{field}[{index}]")
            else:
                path_lists[field].append(entry)
        if len(path_lists[field]) != len(set(path_lists[field])):
            validator.add("MOD-ANALYSIS-001", f"{path}.{field}")
    managed = set(path_lists.get("managedPaths", []))
    generated = set(path_lists.get("generatedPaths", []))
    if any(_glob_covers(l, r) or _glob_covers(r, l) for l in managed for r in generated):
        validator.add("MOD-ANALYSIS-001", path)
    includes = path_lists.get("includePaths", [])
    excludes = path_lists.get("excludePaths", [])
    if includes and all(any(_glob_covers(ex, inc) for ex in excludes) for inc in includes):
        validator.add("MOD-ANALYSIS-001", f"{path}.includePaths")
    llm = value.get("llm")
    llm_fields = {"inputPolicy", "maxPromptTokens", "maxFindingsPerBatch", "wholeGraphPolicy", "requireProvenance"}
    if not validator.object_shape(llm, f"{path}.llm", llm_fields, llm_fields):
        validator.add("MOD-LLM-001", f"{path}.llm")
        return
    valid = (
        llm.get("inputPolicy") == "intent-diff-and-findings"
        and isinstance(llm.get("maxPromptTokens"), int) and not isinstance(llm.get("maxPromptTokens"), bool)
        and 4096 <= llm["maxPromptTokens"] <= 200000
        and isinstance(llm.get("maxFindingsPerBatch"), int) and not isinstance(llm.get("maxFindingsPerBatch"), bool)
        and 1 <= llm["maxFindingsPerBatch"] <= 200
        and llm.get("wholeGraphPolicy") == "reject"
        and llm.get("requireProvenance") is True
    )
    if not valid:
        validator.add("MOD-LLM-001", f"{path}.llm")


def check_conformance(validator: Any, value: Any, path: str) -> None:
    if not validator.object_shape(value, path, {"levels", "commands"}, {"levels", "commands"}):
        return
    levels = value.get("levels")
    allowed_levels = {"document", "graph", "standards", "interfaces", "advisory"}
    if (
        not isinstance(levels, list) or not levels
        or len(levels) != len(set(item for item in levels if isinstance(item, str)))
        or any(not isinstance(item, str) or item not in allowed_levels for item in levels)
    ):
        validator.schema(f"{path}.levels")
    commands = value.get("commands")
    if not isinstance(commands, list) or not commands:
        validator.add("MOD-CONFORMANCE-001", f"{path}.commands")
        return
    for index, command in enumerate(commands):
        if (
            not isinstance(command, list) or not command
            or any(not isinstance(arg, str) or not arg or len(arg) > 1000 for arg in command)
        ):
            validator.add("MOD-CONFORMANCE-001", f"{path}.commands[{index}]")


def check_policies(validator: Any, value: Any, path: str) -> None:
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
    if not validator.object_shape(value, path, allowed, allowed):
        return
    for field, wanted in expected.items():
        if value.get(field) != wanted:
            validator.schema(f"{path}.{field}")
    if not isinstance(value.get("allowDeprecated"), bool):
        validator.schema(f"{path}.allowDeprecated")
