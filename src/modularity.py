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
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))


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

ROOT_FIELDS = {"$schema", "schema", "id", "version", "description", "owners", "standards", "modules", "links", "policies", "analysisScope", "conformance"}
ROOT_REQUIRED = {"schema", "id", "version", "owners", "standards", "modules", "links", "policies", "conformance"}


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


@lru_cache(maxsize=1)
def _catalog() -> dict[str, tuple[str, str]]:
    catalog_path = (
        Path(__file__).resolve().parents[1] / "docs" / "errors" / "catalog.json"
    )
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    return {
        item["code"]: (item["severity"], item["message"]) for item in data["errors"]
    }


def _finding(code: str, path: str) -> Finding:
    severity, message = _catalog()[code]
    return Finding(path=path, code=code, message=message, severity=severity)


def _internal_finding() -> Finding:
    """Return the fail-safe diagnostic without depending on the catalog."""

    return Finding(
        path="$",
        code="MOD-INTERNAL-001",
        message="Validation stopped because of an unexpected internal failure.",
        severity="critical",
    )


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

    def object_shape(self, value: Any, path: str, allowed: set[str], required: set[str]) -> bool:
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
        allowed = {"id", "relation", "status", "repository", "revision", "artifact", "note"}
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
        if value.get("kind") not in {"dsl", "json-schema", "protobuf", "lifecycle", "poa-capability", "twin-trait", "other"}:
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
        if value.get("lifecycle") not in {"experimental", "stable", "deprecated", "retired"}:
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
        from modularity_semantics import check_policies
        check_policies(self, value, path)

    def analysis_scope(self, value: Any, path: str) -> None:
        from modularity_semantics import check_analysis_scope
        check_analysis_scope(self, value, path)

    def conformance(self, value: Any, path: str) -> None:
        from modularity_semantics import check_conformance
        check_conformance(self, value, path)

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
        from modularity_semantics import check_local_digest
        check_local_digest(self, contract, path)

    def semantics(self, document: Any) -> None:
        from modularity_semantics import evaluate_semantics
        evaluate_semantics(self, document)

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
        finding = _internal_finding()
        report = (
            render_json(args.document, [finding])
            if args.format == "json"
            else render_text(args.document, [finding])
        )
        print(report, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
