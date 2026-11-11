"""Dependency-free validator for the Subactor Modularity workspace v1."""

from __future__ import annotations

import argparse
import dataclasses
import errno
import json
import os
import re
import stat
import sys
from collections.abc import Iterable, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_JSON_DEPTH = 64

IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
URI_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*$")
SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
REVISION = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
AUTHORITY = re.compile(r"^authority://[a-z0-9][a-z0-9.-]*(?:/[A-Za-z0-9._~-]+)+$")
LAYER_ORDER = {"foundation": 0, "domain": 1, "application": 2, "interface": 3, "deployment": 4}

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
        return {"code": self.code, "severity": self.severity, "path": self.path, "message": self.message}


@lru_cache(maxsize=1)
def _catalog() -> dict[str, tuple[str, str]]:
    catalog_path = Path(__file__).resolve().parents[1] / "docs" / "errors" / "catalog.json"
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    return {item["code"]: (item["severity"], item["message"]) for item in data["errors"]}


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


def _reject_json_constant(token: str) -> Any:
    raise ValueError(f"Non-finite JSON constant is forbidden: {token}")


def _enforce_json_depth(value: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            raise ValueError("JSON nesting depth exceeds maximum bound")
        if isinstance(current, dict):
            for child in current.values():
                if isinstance(child, (dict, list)):
                    stack.append((child, depth + 1))
        elif isinstance(current, list):
            for child in current:
                if isinstance(child, (dict, list)):
                    stack.append((child, depth + 1))


def read_regular_file_bytes(path: Path) -> bytes:
    """Read a regular non-symlink file within MAX_FILE_BYTES without blocking on FIFOs."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise OSError(errno.EINVAL, "Not a regular file", str(path))
        if st.st_size > MAX_FILE_BYTES:
            raise OSError(errno.EFBIG, "File exceeds maximum byte bound", str(path))
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise OSError(errno.EFBIG, "File exceeds maximum byte bound", str(path))
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def load_json_bytes(raw: bytes) -> Any:
    """Parse strict UTF-8 JSON and reject duplicate keys, NaN/Infinity, and excessive depth."""
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("JSON payload exceeds maximum byte bound")
    text = raw.decode("utf-8", errors="strict")
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except RecursionError as exc:
        raise ValueError("JSON nesting depth exceeds maximum bound") from exc
    _enforce_json_depth(parsed)
    return parsed


def _is_uri(value: Any) -> bool:
    if not isinstance(value, str) or not value or len(value) > 2048:
        return False
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    if not parsed.scheme or not URI_SCHEME.fullmatch(parsed.scheme):
        return False
    if value[len(parsed.scheme) :].startswith("://"):
        return bool(parsed.netloc)
    return bool(parsed.netloc or parsed.path)


def _is_identifier(value: Any) -> bool:
    return isinstance(value, str) and len(value) <= 160 and bool(IDENTIFIER.fullmatch(value))


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
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def _json_identity(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        return f"repr:{type(value).__qualname__}:{value!r}"


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
            if owner.get("kind") not in {"repository", "team", "person"}:
                self.schema(f"{item_path}.kind")
            owner_id = owner.get("id")
            if not isinstance(owner_id, str) or not owner_id or len(owner_id) > 200:
                self.schema(f"{item_path}.id")
            identities.append(_json_identity(owner))
        if len(identities) != len(set(identities)):
            self.schema(path)

    def standard(self, value: Any, path: str) -> None:
        from modularity_semantics import check_standard_shape

        check_standard_shape(self, value, path)

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
        if not self.object_shape(value, path, allowed, {"id", "uri", "kind", "version", "digest"}):
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
            self.object_shape(value, path, {"role", "domain", "owner"}, {"role", "domain", "owner"})
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
        if not isinstance(value.get("layer"), str) or value.get("layer") not in LAYER_ORDER:
            self.schema(f"{path}.layer")
        if not isinstance(value.get("lifecycle"), str) or value.get("lifecycle") not in {"experimental", "stable", "deprecated", "retired"}:
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
        from modularity_semantics import check_link_shape

        check_link_shape(self, value, path)

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
        if "description" in document and (not isinstance(document["description"], str) or not document["description"] or len(document["description"]) > 1000):
            self.schema("$.description")
        self.owners(document.get("owners"), "$.owners")
        standards = document.get("standards")
        if not isinstance(standards, list) or not standards:
            self.schema("$.standards")
        else:
            for index, standard in enumerate(standards):
                self.standard(standard, f"$.standards[{index}]")
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
        document = load_json_bytes(read_regular_file_bytes(path))
    except (OSError, UnicodeDecodeError, ValueError, DuplicateKeyError):
        return [_finding("MOD-JSON-001", "$")]
    return validate_document(document, root=root)


def render_text(path: Path, findings: Sequence[Finding]) -> str:
    if not findings:
        return f"PASS {path}: document,graph,standards"
    return "\n".join(f"{finding.code} {finding.severity} {finding.path}: {finding.message}" for finding in findings)


def render_json(path: Path, findings: Sequence[Finding]) -> str:
    payload = {
        "schema": "subactor.modularity/validation-report/v1",
        "document": str(path),
        "valid": not findings,
        "findings": [finding.as_dict() for finding in findings],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="modularity", description=__doc__)
    parser.add_argument("document", type=Path, help="canonical Modularity workspace JSON")
    parser.add_argument("--root", type=Path, help="optional repository root for digest checks of artifacts that exist locally")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        findings = validate_path(args.document, root=args.root)
        report = render_json(args.document, findings) if args.format == "json" else render_text(args.document, findings)
        sys.stdout.write(f"{report}\n")
        return 1 if findings else 0
    except Exception:  # noqa: BLE001
        finding = _internal_finding()
        report = render_json(args.document, [finding]) if args.format == "json" else render_text(args.document, [finding])
        sys.stderr.write(f"{report}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
