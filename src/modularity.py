"""Dependency-free validator for the Subactor Modularity workspace v1."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Iterable, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import modularity_semantics as _ms
from modularity_io import (
    AUTHORITY,
    DIGEST,
    IDENTIFIER,
    LAYER_ORDER,
    MAX_FILE_BYTES,
    MAX_JSON_DEPTH,
    MAX_JSON_INT_ABS,
    MAX_JSON_INT_DIGITS,
    REVISION,
    SEMVER,
    URI_SCHEME,
    WINDOWS_DRIVE_PREFIX,
    DuplicateKeyError,
    _enforce_json_depth,
    _glob_covers,
    _has_ancestor_symlink,
    _is_digest,
    _is_identifier,
    _is_relative_path,
    _is_revision,
    _is_semver,
    _is_uri,
    _is_utf8,
    _json_identity,
    _valid_prose_str,
    _valid_single_line_str,
    _valid_str,
    load_json_bytes,
    read_regular_file_bytes,
)

__all__ = [
    "AUTHORITY",
    "DIGEST",
    "IDENTIFIER",
    "LAYER_ORDER",
    "MAX_FILE_BYTES",
    "MAX_JSON_DEPTH",
    "MAX_JSON_INT_ABS",
    "MAX_JSON_INT_DIGITS",
    "REVISION",
    "ROOT_FIELDS",
    "ROOT_REQUIRED",
    "SEMVER",
    "URI_SCHEME",
    "WINDOWS_DRIVE_PREFIX",
    "DuplicateKeyError",
    "Finding",
    "Validator",
    "_enforce_json_depth",
    "_glob_covers",
    "_has_ancestor_symlink",
    "_is_digest",
    "_is_identifier",
    "_is_relative_path",
    "_is_revision",
    "_is_semver",
    "_is_uri",
    "_is_utf8",
    "_json_identity",
    "_valid_prose_str",
    "_valid_single_line_str",
    "_valid_str",
    "load_json_bytes",
    "main",
    "read_regular_file_bytes",
    "render_json",
    "render_text",
    "validate_document",
    "validate_path",
]

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


@lru_cache(maxsize=1)
def _catalog() -> dict[str, tuple[str, str]]:
    catalog_path = (
        Path(__file__).resolve().parents[1] / "docs" / "errors" / "catalog.json"
    )
    data = load_json_bytes(read_regular_file_bytes(catalog_path))
    return {
        item["code"]: (item["severity"], item["message"]) for item in data["errors"]
    }


def _finding(code: str, path: str) -> Finding:
    severity, message = _catalog()[code]
    return Finding(path=path, code=code, message=message, severity=severity)


def _internal_finding() -> Finding:
    """Return the fail-safe diagnostic without depending on the catalog."""
    msg = "Validation stopped because of an unexpected internal failure."
    return Finding(path="$", code="MOD-INTERNAL-001", message=msg, severity="critical")


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
        self, value: Any, path: str, allowed: set[str], required: set[str]
    ) -> bool:
        if not isinstance(value, dict):
            self.schema(path)
            return False
        non_str = [key for key in value if not isinstance(key, str)]
        if non_str:
            self.schema(path)
        str_keys = {key for key in value if isinstance(key, str)}
        for key in sorted(str_keys - allowed):
            self.schema(f"{path}.{key}")
        for key in sorted(required - str_keys):
            self.schema(f"{path}.{key}")
        return not non_str

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
            kind = owner.get("kind")
            if not isinstance(kind, str) or kind not in {
                "repository",
                "team",
                "person",
            }:
                self.schema(f"{item_path}.kind")
            if not _valid_single_line_str(owner.get("id"), 200):
                self.schema(f"{item_path}.id")
            identities.append(_json_identity(owner))
        if len(identities) != len(set(identities)):
            self.schema(path)

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
        if not self.object_shape(
            value, path, allowed, {"id", "uri", "kind", "version", "digest"}
        ):
            return
        self.identifier(value.get("id"), f"{path}.id")
        if not _is_uri(value.get("uri")):
            self.schema(f"{path}.uri")
        kind = value.get("kind")
        valid_kinds = {
            "dsl",
            "json-schema",
            "protobuf",
            "lifecycle",
            "poa-capability",
            "twin-trait",
            "other",
        }
        if not isinstance(kind, str) or kind not in valid_kinds:
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
                value, path, {"role", "domain", "owner"}, {"role", "domain", "owner"}
            )
            self.identifier(value.get("domain"), f"{path}.domain")
            self.identifier(value.get("owner"), f"{path}.owner")
        else:
            self.schema(f"{path}.role")

    def module(self, value: Any, path: str) -> None:
        allowed = {"id", "owners", "layer", "lifecycle", "source", "state", "contracts"}
        if not self.object_shape(value, path, allowed, allowed):
            return
        self.identifier(value.get("id"), f"{path}.id")
        self.owners(value.get("owners"), f"{path}.owners")
        if (
            not isinstance(value.get("layer"), str)
            or value.get("layer") not in LAYER_ORDER
        ):
            self.schema(f"{path}.layer")
        if not isinstance(value.get("lifecycle"), str) or value.get(
            "lifecycle"
        ) not in {
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
        if "description" in document and not _valid_prose_str(
            document["description"], 1000
        ):
            self.schema("$.description")
        self.owners(document.get("owners"), "$.owners")
        standards = document.get("standards")
        if not isinstance(standards, list) or not standards:
            self.schema("$.standards")
        else:
            for index, standard in enumerate(standards):
                _ms.check_standard_shape(self, standard, f"$.standards[{index}]")
            identities = [_json_identity(item) for item in standards]
            if len(identities) != len(set(identities)):
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
                _ms.check_link_shape(self, link, f"$.links[{index}]")
        self.policies(document.get("policies"), "$.policies")
        if "analysisScope" in document:
            _ms.check_analysis_scope(self, document["analysisScope"], "$.analysisScope")
        _ms.check_conformance(self, document.get("conformance"), "$.conformance")

    def local_digest(self, contract: dict[str, Any], path: str) -> None:
        _ms.check_local_digest(self, contract, path)

    def validate(self, document: Any) -> list[Finding]:
        self.document_shape(document)
        _ms.evaluate_semantics(self, document)
        return sorted(self.findings)


def validate_document(document: Any, root: Path | None = None) -> list[Finding]:
    return Validator(root=root).validate(document)


def validate_path(path: Path, root: Path | None = None) -> list[Finding]:
    try:
        document = load_json_bytes(read_regular_file_bytes(path, root=root))
    except (OSError, UnicodeDecodeError, TypeError, ValueError, DuplicateKeyError):
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
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
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
        sys.stdout.write(f"{report}\n")
        return 1 if findings else 0
    except Exception:  # noqa: BLE001
        finding = _internal_finding()
        report = (
            render_json(args.document, [finding])
            if args.format == "json"
            else render_text(args.document, [finding])
        )
        sys.stderr.write(f"{report}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
