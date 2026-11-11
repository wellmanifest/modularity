"""Bounded regular-file I/O, strict JSON parsing, and primitive predicates for Modularity v1."""

from __future__ import annotations

import errno
import json
import math
import os
import re
import stat
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_JSON_INT_ABS = 10**400 - 1
MAX_JSON_INT_DIGITS = 400

IDENTIFIER = re.compile(r"\A[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*\Z")
URI_SCHEME = re.compile(r"\A[a-zA-Z][a-zA-Z0-9+.-]*\Z")
SEMVER = re.compile(
    r"\A(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\Z"
)
REVISION = re.compile(r"\A[0-9a-f]{40}\Z")
DIGEST = re.compile(r"\Asha256:[0-9a-f]{64}\Z")
AUTHORITY = re.compile(
    r"\Aauthority://[a-z0-9][a-z0-9.-]*(?:/(?![.]{1,2}(?:/|\Z))[A-Za-z0-9._~-]+)+\Z"
)
WINDOWS_DRIVE_PREFIX = re.compile(r"\A[A-Za-z]:")
LAYER_ORDER = {
    "foundation": 0,
    "domain": 1,
    "application": 2,
    "interface": 3,
    "deployment": 4,
}


class DuplicateKeyError(ValueError):
    """Raised when strict JSON parsing encounters a duplicate object key."""


def _is_utf8(text: str) -> bool:
    try:
        text.encode("utf-8", errors="strict")
        return True
    except UnicodeEncodeError:
        return False


def _valid_str(value: Any, max_len: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= max_len and _is_utf8(value)


def _valid_single_line_str(value: Any, max_len: int) -> bool:
    return _valid_str(value, max_len) and not any(
        ord(ch) < 32 or ord(ch) == 127 for ch in value
    )


def _valid_prose_str(value: Any, max_len: int) -> bool:
    return _valid_str(value, max_len) and not any(
        (ord(ch) < 32 and ch not in ("\n", "\t")) or ord(ch) == 127 for ch in value
    )


def _is_uri(value: Any) -> bool:
    if not _valid_str(value, 2048) or any(
        ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value
    ):
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    if (
        not parsed.scheme
        or not URI_SCHEME.fullmatch(parsed.scheme)
        or ({".", ".."} & set(re.split(r"[/:]", parsed.path)))
    ):
        return False
    if value[len(parsed.scheme) :].startswith("://"):
        return bool(parsed.netloc)
    return bool(parsed.netloc or (parsed.path and "" not in parsed.path.split(":")))


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
    if not _valid_str(value, 500):
        return False
    if (
        value.startswith("/")
        or "\\" in value
        or bool(WINDOWS_DRIVE_PREFIX.match(value))
    ):
        return False
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def _json_identity(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
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


def _cyclic_scc_map(adjacency: dict[str, set[str]]) -> dict[str, int]:
    """Iterative Tarjan SCC returning node -> component_id for all cyclic components."""
    index_counter = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    cyclic_scc: dict[str, int] = {}
    comp_id = 0

    for root in sorted(adjacency):
        if root in indices:
            continue
        indices[root] = lowlink[root] = index_counter
        index_counter += 1
        stack.append(root)
        on_stack.add(root)
        frames: list[tuple[str, list[str], int]] = [
            (root, sorted(adjacency.get(root, set())), 0)
        ]
        while frames:
            node, neighbors, pos = frames[-1]
            if pos < len(neighbors):
                frames[-1] = (node, neighbors, pos + 1)
                nxt = neighbors[pos]
                if nxt not in indices:
                    indices[nxt] = lowlink[nxt] = index_counter
                    index_counter += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    frames.append((nxt, sorted(adjacency.get(nxt, set())), 0))
                elif nxt in on_stack:
                    lowlink[node] = min(lowlink[node], indices[nxt])
            else:
                frames.pop()
                if frames:
                    parent = frames[-1][0]
                    lowlink[parent] = min(lowlink[parent], lowlink[node])
                if lowlink[node] == indices[node]:
                    comp: list[str] = []
                    while True:
                        member = stack.pop()
                        on_stack.remove(member)
                        comp.append(member)
                        if member == node:
                            break
                    if len(comp) > 1 or node in adjacency.get(node, set()):
                        comp_id += 1
                        for member in comp:
                            cyclic_scc[member] = comp_id
    return cyclic_scc


def _require_pos_int(max_bytes: int) -> None:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def _reject_json_constant(token: str) -> Any:
    raise ValueError(f"Non-finite JSON constant is forbidden: {token}")


def _parse_finite_float(token: str) -> float:
    parsed = float(token)
    if not math.isfinite(parsed):
        raise ValueError(f"Non-finite JSON float is forbidden: {token}")
    return parsed


def _parse_bounded_int(token: str) -> int:
    digits = token[1:] if token.startswith(("+", "-")) else token
    if len(digits) > MAX_JSON_INT_DIGITS:
        raise ValueError("JSON integer magnitude exceeds maximum bound")
    parsed = int(token)
    if abs(parsed) > MAX_JSON_INT_ABS:
        raise ValueError("JSON integer magnitude exceeds maximum bound")
    return parsed


def _enforce_json_depth(value: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    if type(max_depth) is not int or max_depth < 1:
        raise ValueError("max_depth must be a positive integer")
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            raise ValueError("JSON nesting depth exceeds maximum bound")
        if isinstance(current, dict):
            for key, child in current.items():
                if not isinstance(key, str):
                    raise TypeError("JSON object keys must be strings")
                if not _is_utf8(key):
                    raise ValueError("Lone UTF-16 surrogate is forbidden in JSON key")
                stack.append((child, depth + 1))
        elif isinstance(current, list):
            for child in current:
                stack.append((child, depth + 1))
        elif isinstance(current, str):
            if not _is_utf8(current):
                raise ValueError("Lone UTF-16 surrogate is forbidden in JSON string")
        elif type(current) is int and abs(current) > MAX_JSON_INT_ABS:
            raise ValueError("JSON integer magnitude exceeds maximum bound")
        elif isinstance(current, float) and not math.isfinite(current):
            raise ValueError("Non-finite JSON float is forbidden")


def _walk_has_symlink(base: Path, parts: Sequence[str]) -> bool:
    cur = base
    for part in parts:
        if part in ("", ".", ".."):
            continue
        cur = cur / part
        if stat.S_ISLNK(os.lstat(cur).st_mode):
            return True
    return False


def _has_ancestor_symlink(path: Path, root: Path | None = None) -> bool:
    raw_start = 3 if path.is_absolute() else 1
    for idx in range(raw_start, len(path.parts)):
        if path.parts[idx - 1] in ("", ".", ".."):
            continue
        if stat.S_ISLNK(os.lstat(Path(*path.parts[:idx])).st_mode):
            return True
    abs_path = Path(os.path.abspath(os.fspath(path)))
    if any(
        stat.S_ISLNK(os.lstat(anc).st_mode)
        for anc in abs_path.parents
        if len(anc.parts) > 2
    ):
        return True
    if root is not None:
        root_res = root.resolve()
        cand = path if path.is_absolute() else (Path.cwd() / path)
        rel = (
            cand.relative_to(root)
            if cand.is_relative_to(root)
            else (cand.relative_to(root_res) if cand.is_relative_to(root_res) else None)
        )
        if rel is not None and _walk_has_symlink(root_res, rel.parts[:-1]):
            return True
    return False


def read_regular_file_bytes(
    path: Path, max_bytes: int = MAX_FILE_BYTES, *, root: Path | None = None
) -> bytes:
    """Read a regular non-symlink file within max_bytes without blocking on FIFOs."""
    _require_pos_int(max_bytes)
    candidate = Path(path)
    if _has_ancestor_symlink(candidate, root):
        raise OSError(errno.ELOOP, "Symlink ancestor is forbidden", str(candidate))
    lst = os.lstat(candidate)
    if stat.S_ISLNK(lst.st_mode):
        raise OSError(errno.ELOOP, "Symlink is forbidden", str(candidate))
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(candidate, flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or (st.st_dev, st.st_ino) != (
            lst.st_dev,
            lst.st_ino,
        ):
            raise OSError(errno.EINVAL, "Not a stable regular file", str(candidate))
        if st.st_size > max_bytes:
            raise OSError(
                errno.EFBIG, "File exceeds maximum byte bound", str(candidate)
            )
        chunks: list[bytes] = []
        total = 0
        while chunk := os.read(fd, min(65536, max_bytes + 1 - total)):
            total += len(chunk)
            if total > max_bytes:
                raise OSError(
                    errno.EFBIG, "File exceeds maximum byte bound", str(candidate)
                )
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def load_json_bytes(raw: bytes, max_bytes: int = MAX_FILE_BYTES) -> Any:
    """Parse strict UTF-8 JSON and reject duplicate keys, NaN/Infinity, and excessive depth."""
    _require_pos_int(max_bytes)
    if len(raw) > max_bytes:
        raise ValueError("JSON payload exceeds maximum byte bound")
    text = raw.decode("utf-8", errors="strict")
    if not _is_utf8(text):
        raise ValueError("Lone UTF-16 surrogate is forbidden in JSON payload")
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
            parse_float=_parse_finite_float,
            parse_int=_parse_bounded_int,
        )
    except RecursionError as exc:
        raise ValueError("JSON nesting depth exceeds maximum bound") from exc
    _enforce_json_depth(parsed)
    return parsed
