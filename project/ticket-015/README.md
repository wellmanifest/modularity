# Ticket 015: Harden modularity JSON overflow/surrogates, rootless ancestor symlinks, and regex anchors

- **ID**: ticket-015
- **Owner**: tom
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-11

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: On 2026-11-11 user authorized auditing, fixing bugs, and hardening across `wellmanifest/*` standard repositories.

Reject `10**400` JSON integer overflow and lone UTF-16 surrogates in `src/modularity.py`, load `docs/errors/catalog.json` via bounded regular-file I/O, enforce positive integer `max_bytes` and bounded `os.read` chunks in `read_regular_file_bytes`, extend `_has_ancestor_symlink` to rootless absolute paths, reject `.` and empty colon/slash URI segments plus `.`/`..` authority segments, anchor all regexes with `\A...\Z`, keep all modules strictly `< 500` lines, and reconcile merged `project/ticket-014/README.md` to `DONE`.

## Acceptance criteria

- [x] AC-01: `load_json_bytes` and `_enforce_json_depth` reject `10**400` integer overflow and lone UTF-16 surrogates across keys and string values, and `_catalog()` loads via `load_json_bytes(read_regular_file_bytes(...))`.
- [x] AC-02: `read_regular_file_bytes` enforces positive integer `max_bytes` and bounded `os.read` chunks, `_has_ancestor_symlink` rejects symlink ancestors for rootless absolute paths, `_is_uri` and `AUTHORITY` reject dot/empty segments, and all regexes use `\A...\Z` anchors while keeping all Python files strictly `< 500` lines.
- [x] AC-03: Regression tests in `tests/test_modularity_hardening.py` pass alongside `ruff check`, `./project/governance-check.sh --base origin/main`, and `wellman check`, and merged `project/ticket-014/README.md` is marked `DONE`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
