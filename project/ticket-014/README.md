# Ticket 014: Harden modularity regular-file inode stability, ancestor symlinks, and URI/path bounds

- **ID**: ticket-014
- **Owner**: tom
- **Status**: DONE
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-11

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: On 2026-11-11 user authorized auditing, fixing bugs, and hardening across `wellmanifest/*` standard repositories.

Enforce `lstat`+`fstat` `(st_dev, st_ino)` inode identity in `read_regular_file_bytes`, reject relative and intra-root ancestor symlinks in `validate_path`, reject `..` traversal in `_is_uri` and Windows drive-prefixed relative paths (`C:foo`) in `_is_relative_path`, anchor all regexes in `src/modularity.py` with `\Z`, keep all modules strictly `< 500` lines, and mark merged `ticket-009` and `ticket-013` `DONE`.

## Acceptance criteria

- [x] AC-01: `read_regular_file_bytes` verifies `lstat`/`fstat` inode identity and `validate_path` rejects ancestor symlink directories with `MOD-JSON-001`.
- [x] AC-02: `_is_uri` rejects `..` path traversal, `_is_relative_path` rejects Windows drive-letter prefixes, all regexes use `\Z` end-of-string anchors, and all Python files stay strictly `< 500` lines.
- [x] AC-03: Regression tests in `tests/test_modularity_hardening.py` pass alongside `ruff check`, `./project/governance-check.sh --base origin/main`, and `wellman check`, and merged `ticket-009` and `ticket-013` are marked `DONE`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
