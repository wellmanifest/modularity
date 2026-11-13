"""Graph, contract, layer, cycle, and state semantic validation for Modularity v1."""

from __future__ import annotations

import fnmatch
import hashlib
from collections import Counter, defaultdict
from typing import Any

from modularity_io import (
    AUTHORITY,
    LAYER_ORDER,
    _cyclic_scc_map,
    _glob_covers,
    _is_digest,
    _is_identifier,
    _is_relative_path,
    _is_revision,
    _is_uri,
    _valid_prose_str,
    _valid_single_line_str,
    read_regular_file_bytes,
)


def check_standard_shape(validator: Any, value: Any, path: str) -> None:
    allowed = {"id", "relation", "status", "repository", "revision", "artifact", "note"}
    if not validator.object_shape(value, path, allowed, {"id", "relation", "status"}):
        return
    validator.identifier(value.get("id"), f"{path}.id")
    relation, status = value.get("relation"), value.get("status")
    if not isinstance(relation, str) or relation not in {"normative", "informative"}:
        validator.schema(f"{path}.relation")
    if not isinstance(status, str) or status not in {"published", "draft"}:
        validator.schema(f"{path}.status")
    if "repository" in value and not _is_uri(value["repository"]):
        validator.schema(f"{path}.repository")
    if "artifact" in value and not _is_relative_path(value["artifact"]):
        validator.add("MOD-PATH-001", f"{path}.artifact")
    if "note" in value and not _valid_prose_str(value["note"], 1000):
        validator.schema(f"{path}.note")
    if relation == "normative":
        if status != "published" or not _is_uri(value.get("repository")):
            validator.add("MOD-STANDARD-001", path)
        if not _is_revision(value.get("revision")) or not _is_relative_path(
            value.get("artifact")
        ):
            validator.add("MOD-STANDARD-001", path)
    elif "revision" in value and not _is_revision(value["revision"]):
        validator.add("MOD-STANDARD-001", f"{path}.revision")
    if status == "draft" and (relation != "informative" or "revision" in value):
        validator.add("MOD-STANDARD-001", path)


def check_conformance(validator: Any, value: Any, path: str) -> None:
    if not validator.object_shape(
        value, path, {"levels", "commands"}, {"levels", "commands"}
    ):
        return
    levels = value.get("levels")
    allowed_levels = {"document", "graph", "standards", "interfaces", "advisory"}
    if (
        not isinstance(levels, list)
        or not levels
        or len(levels) != len({item for item in levels if isinstance(item, str)})
        or any(
            not isinstance(item, str) or item not in allowed_levels for item in levels
        )
    ):
        validator.schema(f"{path}.levels")
    commands = value.get("commands")
    if not isinstance(commands, list) or not commands:
        validator.add("MOD-CONFORMANCE-001", f"{path}.commands")
        return
    for index, command in enumerate(commands):
        if (
            not isinstance(command, list)
            or not command
            or any(not _valid_single_line_str(arg, 1000) for arg in command)
        ):
            validator.add("MOD-CONFORMANCE-001", f"{path}.commands[{index}]")


def check_link_shape(validator: Any, value: Any, path: str) -> None:
    allowed = {"id", "from", "to", "contract", "mode", "authorityRef", "generation"}
    if not validator.object_shape(
        value, path, allowed, {"id", "from", "to", "contract", "mode"}
    ):
        return
    for field in ("id", "from", "to"):
        validator.identifier(value.get(field), f"{path}.{field}")
    if not _is_uri(value.get("contract")):
        validator.schema(f"{path}.contract")
    mode = value.get("mode")
    if not isinstance(mode, str) or mode not in {
        "link",
        "generate",
        "observe",
        "invoke",
    }:
        validator.schema(f"{path}.mode")
    has_authority = "authorityRef" in value
    if mode == "invoke":
        if (
            not has_authority
            or not isinstance(value.get("authorityRef"), str)
            or not AUTHORITY.fullmatch(value["authorityRef"])
        ):
            validator.add("MOD-AUTH-001", f"{path}.authorityRef")
    elif has_authority:
        validator.add("MOD-AUTH-001", f"{path}.authorityRef")
    has_generation = "generation" in value
    if mode == "generate":
        generation = value.get("generation")
        if not isinstance(generation, dict):
            validator.add("MOD-COMPOSE-001", f"{path}.generation")
        else:
            validator.object_shape(
                generation,
                f"{path}.generation",
                {"generator", "outputContract"},
                {"generator", "outputContract"},
            )
            validator.identifier(
                generation.get("generator"), f"{path}.generation.generator"
            )
            if not _is_uri(generation.get("outputContract")):
                validator.schema(f"{path}.generation.outputContract")
            if not _is_identifier(generation.get("generator")) or not _is_uri(
                generation.get("outputContract")
            ):
                validator.add("MOD-COMPOSE-001", f"{path}.generation")
    elif has_generation:
        validator.add("MOD-COMPOSE-001", f"{path}.generation")


def check_local_digest(validator: Any, contract: dict[str, Any], path: str) -> None:
    relative = contract.get("path")
    digest = contract.get("digest")
    if (
        validator.root is None
        or not _is_relative_path(relative)
        or not _is_digest(digest)
    ):
        return
    raw_candidate = validator.root / relative
    probe = raw_candidate
    while True:
        try:
            if probe.is_symlink():
                validator.add("MOD-PATH-001", f"{path}.path")
                return
        except OSError:
            validator.add("MOD-PATH-001", f"{path}.path")
            return
        if probe == validator.root or probe.parent == probe:
            break
        probe = probe.parent
    try:
        has_entry = raw_candidate.exists()
        candidate = raw_candidate.resolve(strict=has_entry)
        candidate.relative_to(validator.root)
    except (OSError, RuntimeError, ValueError):
        validator.add("MOD-PATH-001", f"{path}.path")
        return
    if not has_entry:
        return
    try:
        raw_bytes = read_regular_file_bytes(candidate)
    except OSError:
        validator.add("MOD-PATH-001", f"{path}.path")
        return
    observed = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    if observed != digest:
        validator.add("MOD-DIGEST-001", f"{path}.digest")


def evaluate_semantics(validator: Any, document: Any) -> None:
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

    all_ids = [item["id"] for item in modules] + [
        item["id"] for item in links if _is_identifier(item.get("id"))
    ]
    duplicate_ids = {item for item, count in Counter(all_ids).items() if count > 1}
    for module in modules:
        if module["id"] in duplicate_ids:
            validator.add("MOD-ID-001", f"{module_paths[id(module)]}.id")
    for link in links:
        link_id = link.get("id")
        if isinstance(link_id, str) and link_id in duplicate_ids:
            validator.add("MOD-ID-001", f"{link_paths[id(link)]}.id")

    module_by_id: dict[str, dict[str, Any]] = {}
    for module in modules:
        module_by_id.setdefault(module["id"], module)

    contracts_by_uri: dict[str, list[tuple[dict[str, Any], dict[str, Any], str]]] = (
        defaultdict(list)
    )
    for module in modules:
        module_path = module_paths[id(module)]
        contracts = module.get("contracts")
        if not isinstance(contracts, list):
            continue
        local_ids = [
            item["id"]
            for item in contracts
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        duplicate_local = {
            item for item, count in Counter(local_ids).items() if count > 1
        }
        for index, contract in enumerate(contracts):
            if not isinstance(contract, dict):
                continue
            contract_path = f"{module_path}.contracts[{index}]"
            cid = contract.get("id")
            if isinstance(cid, str) and cid in duplicate_local:
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
        consumer = (
            module_by_id.get(consumer_id) if isinstance(consumer_id, str) else None
        )
        provider = (
            module_by_id.get(provider_id) if isinstance(provider_id, str) else None
        )
        if consumer is None:
            validator.add("MOD-LINK-001", f"{link_path}.from")
        if provider is None:
            validator.add("MOD-LINK-001", f"{link_path}.to")
        if consumer is not None and consumer_id == provider_id:
            validator.add("MOD-LINK-002", link_path)
        if consumer is None or provider is None:
            continue
        assert isinstance(consumer_id, str) and isinstance(provider_id, str)
        adjacency[consumer_id].add(provider_id)
        contract_uri = link.get("contract")
        provider_exports = [
            item
            for item in (
                contracts_by_uri.get(contract_uri, [])
                if isinstance(contract_uri, str)
                else []
            )
            if item[0].get("id") == provider_id
        ]
        if len(provider_exports) != 1:
            validator.add("MOD-CONTRACT-002", f"{link_path}.contract")
            contract = None
        else:
            contract = provider_exports[0][1]
        c_layer = consumer.get("layer")
        p_layer = provider.get("layer")
        consumer_layer = LAYER_ORDER.get(c_layer) if isinstance(c_layer, str) else None
        provider_layer = LAYER_ORDER.get(p_layer) if isinstance(p_layer, str) else None
        if (
            consumer_layer is not None
            and provider_layer is not None
            and consumer_layer < provider_layer
        ):
            validator.add("MOD-LAYER-001", link_path)
        lifecycle = provider.get("lifecycle")
        if lifecycle == "retired":
            validator.add("MOD-LIFECYCLE-001", link_path)
        if (
            lifecycle == "deprecated"
            and isinstance(document.get("policies"), dict)
            and document["policies"].get("allowDeprecated") is False
        ):
            validator.add("MOD-LIFECYCLE-002", link_path)
        if (
            contract is not None
            and contract.get("kind") == "twin-trait"
            and link.get("mode") != "observe"
        ):
            validator.add("MOD-TWIN-001", link_path)
        if (
            contract is not None
            and contract.get("kind") == "poa-capability"
            and link.get("mode") != "invoke"
        ):
            validator.add("MOD-POA-001", link_path)
        generation = link.get("generation")
        if link.get("mode") == "generate" and isinstance(generation, dict):
            generator_id = generation.get("generator")
            if _is_identifier(generator_id) and generator_id not in module_by_id:
                validator.add("MOD-COMPOSE-001", f"{link_path}.generation.generator")
            out_uri = generation.get("outputContract")
            output_exports = (
                contracts_by_uri.get(out_uri, []) if isinstance(out_uri, str) else []
            )
            if (
                len(output_exports) != 1
                or output_exports[0][1].get("uri") == contract_uri
                or (
                    _is_identifier(generator_id)
                    and generator_id in module_by_id
                    and output_exports[0][0].get("id") != generator_id
                )
            ):
                validator.add(
                    "MOD-COMPOSE-001", f"{link_path}.generation.outputContract"
                )

    cyclic_scc = _cyclic_scc_map(adjacency)
    for link in links:
        src_id, dst_id = link.get("from"), link.get("to")
        if (
            isinstance(src_id, str)
            and isinstance(dst_id, str)
            and src_id in cyclic_scc
            and cyclic_scc.get(src_id) == cyclic_scc.get(dst_id)
        ):
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
        owners = state_owners.get(domain, []) if isinstance(domain, str) else []
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
                    c["path"]
                    for c in contracts
                    if isinstance(c, dict) and isinstance(c.get("path"), str)
                )
        if any(
            fnmatch.fnmatchcase(p, pat)
            for p in protected_paths
            for pat in excluded
            if isinstance(pat, str)
        ):
            validator.add("MOD-ANALYSIS-001", "$.analysisScope.excludePaths")


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
    if any(
        _glob_covers(left, right) or _glob_covers(right, left)
        for left in managed
        for right in generated
    ):
        validator.add("MOD-ANALYSIS-001", path)
    includes = path_lists.get("includePaths", [])
    excludes = path_lists.get("excludePaths", [])
    if includes and all(
        any(_glob_covers(ex, inc) for ex in excludes) for inc in includes
    ):
        validator.add("MOD-ANALYSIS-001", f"{path}.includePaths")
    llm = value.get("llm")
    llm_fields = {
        "inputPolicy",
        "maxPromptTokens",
        "maxFindingsPerBatch",
        "wholeGraphPolicy",
        "requireProvenance",
    }
    if not validator.object_shape(llm, f"{path}.llm", llm_fields, llm_fields):
        validator.add("MOD-LLM-001", f"{path}.llm")
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
        validator.add("MOD-LLM-001", f"{path}.llm")
